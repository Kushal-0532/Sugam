"""Jev decision logic with a stubbed API (no network): when Jev acts, and every path that hands the step to Groq."""
from src import agent, jev

ELS = [dict(id=0, text="Search", desc="", rid="", cls="EditText", click=True, edit=True, scroll=False, cx=1, cy=1),
       dict(id=1, text="", desc="Timer", rid="timer", cls="FrameLayout", click=True, edit=False, scroll=False, cx=2, cy=2),
       dict(id=2, text="", desc="", rid="list", cls="RecyclerView", click=False, edit=False, scroll=True, cx=3, cy=3)]
ALLOW = {"clock": {"pkg": "com.oneplus.deskclock", "aliases": []}, "calculator": {"pkg": "com.oneplus.calculator"}}


def stub(monkeypatch, action, conf=0.95, element="1", el_conf=0.95, app="clock", outward=0.01):
    def fake(state, q, timeout=10):
        stub.q = q
        return {"action": {"choice": action, "confidence": conf},
                "element": {"choice": element, "confidence": el_conf},
                "app": {"choice": app, "confidence": 0.9}, "outward": {"noul": outward}}, 0.4
    monkeypatch.setattr(jev, "ask", fake)


def step():
    return jev.step("open the timer", ELS, [], ALLOW, lambda k: k)


def test_options_given_to_jev(monkeypatch):
    stub(monkeypatch, "tap")
    step()
    assert set(stub.q) == {"action", "element", "app", "outward"}
    assert set(stub.q["element"]["criteria"]) == {"0", "1", "2"} and stub.q["element"]["criteria"]["1"] == "Timer"
    assert stub.q["outward"]["type"] == "noul" and set(stub.q["app"]["criteria"]) == set(ALLOW)


def test_confident_picks_become_valid_actions(monkeypatch):
    stub(monkeypatch, "tap")
    a, info = step()
    assert a["action"] == "tap" and a["element_id"] == 1 and info["outward"] == 0.01
    stub(monkeypatch, "open_app", app="calculator")
    assert step()[0]["app"] == "com.oneplus.calculator"
    stub(monkeypatch, "done")
    assert step()[0]["action"] == "done"
    stub(monkeypatch, "back")
    assert step()[0]["action"] == "back"


def test_swipe_uses_the_list_only_if_scrollable(monkeypatch):
    stub(monkeypatch, "swipe_up", element="2")
    a, _ = step()
    assert a["direction"] == "up" and a["element_id"] == 2
    stub(monkeypatch, "swipe_down", element="1")
    a, _ = step()
    assert a["direction"] == "down" and "element_id" not in a


def test_hands_to_groq(monkeypatch):
    for kw, why in (({"action": "type"}, "text needed"), ({"action": "fail"}, "groq gets one try"),
                    ({"action": "tap", "conf": 0.5}, "low action confidence"),
                    ({"action": "tap", "el_conf": 0.59}, "low element confidence"),
                    ({"action": "tap", "element": "99"}, "invalid jev pick")):
        stub(monkeypatch, **kw)
        a, info = step()
        assert a is None and why in info["why"], kw

    def boom(*_, **__):
        raise RuntimeError("502")
    monkeypatch.setattr(jev, "ask", boom)
    a, info = step()
    assert a is None and "jev error" in info["why"]


def test_jev_decides_the_task(monkeypatch):
    def route(task, conf=0.95, app="calculator", app_conf=0.95):
        monkeypatch.setattr(jev, "route", lambda *_: ({"task": task, "conf": conf, "app": app, "app_conf": app_conf}, 0.4))

    # no details needed: Groq is skipped
    route("wifi_settings")
    assert agent.jev_decide("WiFi settings खोलो।", None) == ({"task": "wifi_settings", "lang": "hi", "goal": "WiFi settings खोलो।"}, None)
    route("open_app")
    r, pin = agent.jev_decide("calculator open చేయి.", None)
    assert r["task"] == "open_app" and r["pkg"] == "com.oneplus.calculator" and r["lang"] == "te" and pin is None
    route("agent")
    assert agent.jev_decide("x", None)[0]["task"] == "agent"
    # details needed: Jev's task is pinned, Groq only fills in the details
    for task in ("alarm", "chrome_search", "message"):
        route(task)
        assert agent.jev_decide("x", None) == (None, task)
    # unsure: Groq decides everything
    for args in (("alarm", 0.79), ("wifi_settings", 0.79), ("open_app", 0.95, "clock", 0.5)):
        route(*args)
        assert agent.jev_decide("x", None) == (None, None), args

    def boom(*_):
        raise RuntimeError("502")
    monkeypatch.setattr(jev, "route", boom)
    assert agent.jev_decide("x", None) == (None, None)
