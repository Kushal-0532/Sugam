"""uiautomator2 wrapper. No installs: text entry uses set_text (accessibility), clipboard fallback."""
import time
import uiautomator2 as u2
from .screen import compact

SWIPE_PX = 250  # ponytail: fixed distance; scale by element size if pickers need it


def connect(serial=None):
    try:
        return u2.connect(serial)
    except Exception as e:
        raise RuntimeError(f"phone connect failed ({e}). Check `adb devices`: unauthorized -> accept RSA prompt; offline -> replug.")


def current(d):
    i = d.app_current()
    return {"package": i.get("package"), "activity": i.get("activity")}


def snapshot(d):
    """-> (elements, hash, package)"""
    return compact(d.dump_hierarchy(), size=d.window_size())


def settle(d, tries=10, gap=0.3):
    """Poll until the screen hash is the same twice in a row (max ~3 s)."""
    last = None
    for _ in range(tries):
        h = snapshot(d)[1]
        if h == last:
            return h
        last = h
        time.sleep(gap)
    return last


def execute(d, a, elements, allowlist_pkgs=()):
    """Run one validated action. Returns None, or an error string."""
    act = a["action"]
    if act in ("tap", "type"):
        e = elements[a["element_id"]]
        d.click(e["cx"], e["cy"])
        if act == "type":
            time.sleep(0.3)
            f = d(focused=True)
            if f.exists:
                f.set_text(a["text"])
            else:
                d.set_clipboard("t", a["text"]); d.shell("input keyevent 279")  # KEYCODE_PASTE
    elif act == "swipe":
        if "element_id" in a:  # swipe inside the element (pickers/lists), not the whole screen
            e = elements[a["element_id"]]
            dx, dy = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}[a["direction"]]
            for _ in range(a.get("repeat", 1)):  # one LLM call can scroll many notches
                d.swipe(e["cx"], e["cy"], e["cx"] + dx * SWIPE_PX, e["cy"] + dy * SWIPE_PX, duration=0.25)
        else:
            d.swipe_ext(a["direction"])
    elif act in ("back", "home"):
        d.press(act)
    elif act == "open_app":
        d.app_start(a["app"])
    elif act == "wait":
        time.sleep(1)
    return None

