"""Визуальный/математический тест синусоидальной дрожи (Итерация 2.2).

Проверяет три требования пользователя:
1. Математическая гарантия возврата: производная осевой компоненты меняет
   знак минимум 2 раза за каждый drag;
2. Финальная точка drag достигается с точностью ±1 px (гауссово окно);
3. Каждый drag уникален (рандомизация амплитуд и фаз).

Дополнительно (опционально) пишет траекторию одного representative-drag'а
в CSV (tests/wobble_trajectory.csv) и, если доступен matplotlib, сохраняет
график (tests/wobble_trajectory.png).

Запуск:  python tests/test_sinusoidal_wobble.py
"""
import sys, os, types, math, csv, time

# ---------- Мок pyautogui (headless) ----------
moves = []
pg = types.ModuleType("pyautogui")
pg.position = lambda: (10, 10)
pg.size = lambda: (1920, 1080)
pg.moveTo = lambda x, y, *a, **k: moves.append((float(x), float(y)))
pg.click = lambda *a, **k: None
pg.mouseDown = lambda *a, **k: None
pg.mouseUp = lambda *a, **k: None
pg.scroll = lambda *a, **k: None
sys.modules["pyautogui"] = pg
time.sleep = lambda s: None

os.environ["HUMANIZE_ENABLED"] = "true"
sys.path.insert(0, "/workspace/OSROKBOT/Classes")
from utils.humanizer import Humanizer  # noqa: E402

AXES = [(1.0, 0.0), (0.0, 1.0), (math.sqrt(0.5), math.sqrt(0.5)),
        (-math.sqrt(0.5), math.sqrt(0.5))]


def axis_sign_changes(points, start, end):
    """Число смен знака производной проекции на главную ось drag'а."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    L = math.hypot(dx, dy) or 1.0
    ux, uy = dx / L, dy / L
    proj = [px * ux + py * uy for px, py in points]
    diffs = [proj[i + 1] - proj[i] for i in range(len(proj) - 1)]
    changes = 0
    prev = 0
    for v in diffs:
        s = 1 if v > 0 else (-1 if v < 0 else 0)
        if s != 0 and prev != 0 and s != prev:
            changes += 1
        if s != 0:
            prev = s
    return changes


def main():
    h = Humanizer.get()
    N = 100
    sig_changes = []
    final_errs = []
    trajectories = {}

    for run in range(N):
        ax, ay = AXES[run % len(AXES)]
        dist = [180.0, 250.0, 400.0][run % 3]
        start = (300.0, 200.0)
        end = (start[0] + ax * dist, start[1] + ay * dist)
        del moves[:]
        h.human_drag(start, end)

        # 1. Гарантия возврата: >= 2 смены знака производной за drag
        sc = axis_sign_changes(moves, start, end)
        sig_changes.append(sc)
        assert sc >= 2, f"drag {run}: всего {sc} смен знака производной (< 2)"

        # 2. Финал ±1 px
        err = math.hypot(moves[-1][0] - end[0], moves[-1][1] - end[1])
        final_errs.append(err)
        assert err <= 1.0, f"drag {run}: финал вне ±1 px (err={err:.3f})"

        # 3. Уникальность — сохраняем отпечатки первых 6 траекторий
        if run < 6:
            trajectories[run] = list(moves)

    # Уникальность: ни одна пара траекторий не совпадает поточно
    fps = {}
    for run, tr in trajectories.items():
        fp = tuple(round(v, 4) for xy in tr[:40] for v in xy)
        assert fp not in fps.values(), f"drag {run} не уникален"
    uniq = len(set(tuple(xy for xy in tr) for tr in trajectories.values()))
    assert uniq == len(trajectories), "траектории дублируются"

    print(f"N={N} | смены знака производной: min={min(sig_changes)}, "
          f"avg={sum(sig_changes)/len(sig_changes):.1f}")
    print(f"максимальная ошибка финала: {max(final_errs):.6f} px (<= 1 px)")
    print("UNIQUENESS OK: все траектории различаются (A1/A2/phi рандомизированы)")

    # --- Опционально: CSV + график representative-драга ---
    csv_path = os.path.join(os.path.dirname(__file__), "wobble_trajectory.csv")
    tr = trajectories[0]
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["frame", "x", "y"])
        for i, (x, y) in enumerate(tr):
            w.writerow([i, f"{x:.3f}", f"{y:.3f}"])
    print(f"CSV сохранён: {csv_path} ({len(tr)} кадров)")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        png_path = os.path.join(os.path.dirname(__file__), "wobble_trajectory.png")
        xs, ys = zip(*tr)
        fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 7))
        a1.plot(xs, ys, lw=0.8)
        a1.axhline(200, color="gray", ls="--", lw=0.5)
        a1.set_title("Drag trajectory (sinusoidal double-frequency wobble)")
        a1.set_xlabel("x, px"); a1.set_ylabel("y, px")
        t = range(len(xs))
        a2.plot(t, xs, lw=0.8, label="axis projection (along drag)")
        a2.plot(t, ys, lw=0.8, label="perpendicular")
        a2.set_title("Frame series: A1*sin windowed along + A2*sin perp, Gaussian envelope")
        a2.legend(); a2.set_xlabel("frame")
        fig.tight_layout()
        fig.savefig(png_path, dpi=110)
        print(f"График сохранён: {png_path}")
    except ImportError:
        print("matplotlib недоступен — график пропущен (CSV достаточно)")

    print("SINUSOIDAL WOBBLE TEST PASSED")


if __name__ == "__main__":
    main()
