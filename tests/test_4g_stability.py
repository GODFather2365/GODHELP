"""Headless-тест стабилизации TEST4g (Вариант 1: kick от позиции курсора).

Детектор «возвратного микродвижения» — строгий, как в античит-эвристике:
для каждого соседнего сегмента траектории считаем проекции перемещений на
главную ось drag'а; возврат = следующая проекция отрицательна при
положительной предыдущей и |отрицательной| >= 0.3 * предыдущей (шум кривой
Безье по перпендикуляру не учитываем — берём только осевую компоненту).

Требование пользователя: TEST4g должен проходить в 100% прогонов,
минимум 50 тестовых запусков. Запускаем N=200 drag'ов и проверяем, что
КАЖДЫЙ drag содержит >= 1 возвратный микросегмент (гарантия, а не статистика).
"""
import sys, os, types, math, time

# ---------- Мок pyautogui ----------
moves = []          # фактическая последовательность moveTo
pg = types.ModuleType("pyautogui")
pg.position = lambda: (10, 10)
pg.size = lambda: (1920, 1080)
pg.moveTo = lambda x, y, *a, **k: moves.append((float(x), float(y)))
pg.click = lambda *a, **k: None
pg.mouseDown = lambda *a, **k: None
pg.mouseUp = lambda *a, **k: None
pg.scroll = lambda *a, **k: None
sys.modules["pyautogui"] = pg

# time.sleep -> no-op, чтобы 200 drag'ов проходили мгновенно
_real_sleep = time.sleep
time.sleep = lambda s: None

os.environ["HUMANIZE_ENABLED"] = "true"
sys.path.insert(0, "/workspace/OSROKBOT/Classes")
from utils.humanizer import Humanizer, HumanizerConfig

cfg = HumanizerConfig.from_env()
assert abs(cfg.drag_wobble_px - 3.0) < 1e-9, \
    f"drag_wobble_px должен быть 3.0 по умолчанию, получено {cfg.drag_wobble_px}"

AXES = [(1.0, 0.0), (0.0, 1.0), (math.sqrt(0.5), math.sqrt(0.5)), (-math.sqrt(0.5), math.sqrt(0.5))]

def reversals(points, start, end):
    """Кол-во возвратных микросегментов вдоль главной оси drag'а."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    L = math.hypot(dx, dy) or 1.0
    ux, uy = dx / L, dy / L
    proj = [px * ux + py * uy for px, py in points]
    diffs = [proj[i + 1] - proj[i] for i in range(len(proj) - 1)]
    revs = 0
    for i in range(1, len(diffs)):
        a, b = diffs[i - 1], diffs[i]
        if a > 0.5 and b < 0 and abs(b) >= 0.3 * a:
            revs += 1
    return revs

N_RUNS = 200  # > требуемых 50
fail_cases = []
rev_counts = []
for run in range(N_RUNS):
    start = (300.0, 200.0)
    ax, ay = AXES[run % len(AXES)]
    dist = [180.0, 250.0, 400.0][run % 3]  # короткие/средние/длинные drag'и
    end = (start[0] + ax * dist, start[1] + ay * dist)
    del moves[:]
    h = Humanizer.get()
    h.human_drag(start, end)
    assert len(moves) > 10, "слишком мало точек moveTo"
    # финальная точка точная
    assert abs(moves[-1][0] - round(end[0])) <= 1 and abs(moves[-1][1] - round(end[1])) <= 1, \
        f"drag не завершился в целевой точке: {moves[-1]} vs {end}"
    r = reversals(moves, start, end)
    rev_counts.append(r)
    if r == 0:
        fail_cases.append(run)

min_r, max_r = min(rev_counts), max(rev_counts)
print(f"N={N_RUNS} drag'ов | возвратов на drag: min={min_r}, max={max_r}, "
      f"avg={sum(rev_counts)/len(rev_counts):.2f}")
if fail_cases:
    print(f"FAILED: {len(fail_cases)} drag'ов без возвратного микродвижения: {fail_cases[:10]}")
    sys.exit(1)
print("TEST4g STABILIZED: 100% drag'ов содержат возвратное микро-дрожание (Variance-safe).")
