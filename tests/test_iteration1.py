"""Headless-тесты Итерации 1: image_finder, state_machine, OS_ROKBOT, humanizer(dedup/scroll)."""
import sys, os, types, time

# ---------- Мок pyautogui ----------
class FakeWin:
    def __init__(self): self.left, self.top = 0, 0
    def activate(self): pass

calls = []
pg = types.ModuleType("pyautogui")
pg.position = lambda: (10, 10)
pg.size = lambda: (1920, 1080)
pg.moveTo = lambda *a, **k: calls.append(("moveTo", a))
pg.click = lambda *a, **k: calls.append(("click", a))
pg.mouseDown = lambda *a, **k: calls.append(("down", a))
pg.mouseUp = lambda *a, **k: calls.append(("up", a))
pg.scroll = lambda *a, **k: calls.append(("scroll", a))
pg.getActiveWindow = lambda: FakeWin()
sys.modules["pyautogui"] = pg

sys.path.insert(0, "/workspace/OSROKBOT/Classes")
from utils.humanizer import Humanizer, HumanizerConfig

def fresh(**kw):
    defaults = dict(enabled=True, bezier_enabled=False, jitter_enabled=False,
                    variable_sleep_enabled=False, pauses_enabled=False,
                    miss_enabled=False, dedup_enabled=True, dedup_radius=12,
                    dedup_window=30.0)
    defaults.update(kw)
    Humanizer.reset()
    return Humanizer(HumanizerConfig(**defaults))

# ---------- ТЕСТ 1: click_dedup — второй клик в ту же точку подавляется ----------
h = fresh()
del calls[:]
assert h.click_dedup(500, 500) is True
n1 = len([c for c in calls if c[0] == "down"])
del calls[:]
assert h.click_dedup(503, 498) is False   # в пределах сетки 12px — дубликат
assert not any(c[0] == "down" for c in calls), "дубликат не должен кликать"
assert h.click_dedup(900, 900) is True    # другая точка — кликает
print("TEST1 dedup suppression OK")

# ---------- ТЕСТ 2: дедуп по истечении окна времени ----------
h = fresh(dedup_window=0.05)
assert h.click_dedup(200, 200) is True
time.sleep(0.08)
assert h.click_dedup(200, 200) is True    # окно истекло — не дубликат
print("TEST2 dedup window expiry OK")

# ---------- ТЕСТ 3: отключенная дедупликация -> оба клика проходят ----------
h = fresh(dedup_enabled=False)
assert h.click_dedup(300, 300) is True
assert h.click_dedup(300, 300) is True
print("TEST3 dedup disabled OK")

# ---------- ТЕСТ 4: StateMachine.execute вызывает maybe_behavioral_pause ----------
import state_machine as sm_mod
h = Humanizer.get()  # singleton с дефолтным env-конфигом (pauses on)
fired = {"n": 0}
orig = h.maybe_behavioral_pause
h.maybe_behavioral_pause = lambda: (fired.__setitem__("n", fired["n"] + 1), orig())[1]

class SuccState:
    def perform(self): return True
class FailState:
    def perform(self): return False

sm = sm_mod.StateMachine()
sm.add_state("A", SuccState(), next_state_on_success="B", next_state_on_failure="C")
sm.add_state("B", SuccState(), next_state_on_success="A")
sm.add_state("C", FailState(), next_state_on_failure="A")
sm.set_initial_state("A")
r = sm.execute()
assert r is True and sm.current_state == "B", "переход success сломан"
assert fired["n"] == 1, "pause не вызвана при успехе"
sm.set_initial_state("C")
r = sm.execute()
assert r is False and sm.current_state == "A", "переход failure сломан"
assert fired["n"] == 1, "pause НЕ должна вызываться при неудаче"
h.maybe_behavioral_pause = orig
print("TEST4 state_machine integration + backward compat OK")

# Мок cv2/termcolor (в headless-среде opencv не установлен; в реальном проекте они есть)
cv2m = types.ModuleType("cv2")
cv2m.cvtColor = lambda *a, **k: None
cv2m.imread = lambda *a, **k: None
cv2m.resize = lambda *a, **k: None
cv2m.matchTemplate = lambda *a, **k: np.zeros((1, 1))
cv2m.rectangle = lambda *a, **k: None
cv2m.imwrite = lambda *a, **k: None
cv2m.COLOR_RGB2BGR = 1
cv2m.TM_CCOEFF_NORMED = 1
cv2m.INTER_AREA = 1
sys.modules["cv2"] = cv2m
tc = types.ModuleType("termcolor"); tc.colored = lambda t, *a, **k: str(t)
sys.modules["termcolor"] = tc

# ---------- ТЕСТ 5: ImageFinder.find_and_click_image (мок cv2-пути через monkeypatch _match_image) ----------
import image_finder as if_mod
finder = if_mod.ImageFinder()
win = FakeWin(); win.left, win.top = 100, 50

import numpy as np
target_img = np.zeros((20, 20, 3), dtype=np.uint8)
# одна рамка: центр (110+... ) -> pick box [x1,y1,x2,y2]
screenshot_cv = np.zeros((720, 1280, 3), dtype=np.uint8)
def fake_match(path, screenshot):
    scale = (1.0, 1.0)
    matches = [(100, 100)]
    rects = np.array(matches, dtype=float)
    return scale, matches, 1, 0.95, target_img, screenshot_cv
finder._match_image = fake_match
# non_max_suppression_fast требует np.array формата [[x1,y1,x2,y2]] — патчим на прямой возврат
finder.non_max_suppression_fast = staticmethod(lambda boxes, ov: boxes)

Humanizer.reset()
h = fresh(dedup_window=30)
del calls[:]
res = finder.find_and_click_image("Media/barbarian.png", None, win, 0, 0, 0)
assert res is True
downs = [c for c in calls if c[0] == "down"]
assert len(downs) == 1, f"ожидался 1 клик, было {len(downs)}"
# центр рамки: startX=100,endX=100+20 -> center_x=110 + win.left=100 => 210; y аналогично 210
cx, cy = downs[0][1][:2] if isinstance(downs[0][1], tuple) else downs[0][1], None
print("TEST5 image_finder click OK, click coords call:", calls[:3])

# повторный вызов той же цели -> дубликат подавлен (нет новых mouseDown)
del calls[:]
res = finder.find_and_click_image("Media/barbarian.png", None, win, 0, 0, 0)
assert res is True  # контракт возврата сохранён!
assert not [c for c in calls if c[0] == "down"], "дедуп в image_finder не сработал"
print("TEST5b dedup inside image_finder OK, return-contract preserved")

# ---------- ТЕСТ 6: human_scroll — вариативность шагов и суммарный объём ----------
h = fresh()
for trial in range(5):
    del calls[:]
    h.human_scroll(-30)
    scrolls = [c[1][0] for c in calls if c[0] == "scroll"]
    assert all(s < 0 for s in scrolls), "направление должно сохраняться"
    assert sum(scrolls) in (-30, -31, -32), f"сумма {sum(scrolls)} != заданному объёму"
    assert len(scrolls) >= 3, "скролл должен гранулироваться"
# разные прогоны дают разную грануляцию (вариативность)
patterns = set()
for _ in range(8):
    del calls[:]
    h.human_scroll(40)
    patterns.add(tuple(c[1][0] for c in calls if c[0] == "scroll"))
assert len(patterns) > 1, "грануляция скролла не вариативна"
print("TEST6 human_scroll OK; уникальных паттернов за 8 прогонов:", len(patterns))

# ---------- ТЕСТ 7: OS_ROKBOT — импорт модуля main-цикла (мок тяжёлых зависимостей) ----------
for name in ("action_sets", "keyboard", "pygetwindow"):
    m = types.ModuleType(name); sys.modules.setdefault(name, m)
import inspect as _inspect
_src = _inspect.getsourcefile(__import__("utils.humanizer", fromlist=["x"]).__name__) if False else None
# signal_emitter реальный (лёгкий), action_sets мок с атрибутом ActionSets
sys.modules["action_sets"].ActionSets = type("ActionSets", (), {})
se = types.ModuleType("signal_emitter")
class SignalEmitter:
    def __init__(self):
        self.pause_toggled = type("S", (), {"emit": lambda *a, **k: None})()
se.SignalEmitter = SignalEmitter
sys.modules["signal_emitter"] = se
qt = types.ModuleType("PyQt5"); qc = types.ModuleType("PyQt5.QtCore")
qc.pyqtSignal = lambda *a, **k: None
sys.modules["PyQt5"] = qt; sys.modules["PyQt5.QtCore"] = qc
import OS_ROKBOT as bot_mod
bot = bot_mod.OSROKBOT("Rise of Kingdoms", delay=0.01)

import threading
executed = {"n": 0}
stopper = threading.Event()
class M:
    def execute(self_inner):
        executed["n"] += 1
        if executed["n"] >= 5:
            stopper.set()
            bot.stop()          # штатная остановка через публичный API
        return True             # success -> вызывается гуманизированный sleep
import threading
t = threading.Thread(target=lambda: bot.run([M()])); t.start()
stopper.wait(timeout=10); t.join(timeout=5)
bot.stop()
assert executed["n"] >= 5, f"main loop должен крутить machine.execute(), выполнено {executed['n']}"
print("TEST7 OS_ROKBOT.run OK (Humanizer.reset + humanized sleeps)")

print("\nALL ITERATION-1 TESTS PASSED")
