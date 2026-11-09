import copy
import pytest
from src.actions import validate

EL = [{}, {}, {}]
AL = {"com.google.android.youtube"}
OK = {
    "tap": {"action": "tap", "element_id": 1},
    "type": {"action": "type", "element_id": 2, "text": "hi"},
    "swipe": {"action": "swipe", "direction": "up"},
    "open_app": {"action": "open_app", "app": "com.google.android.youtube"},
    "ask_user": {"action": "ask_user"},
    "back": {"action": "back"}, "home": {"action": "home"}, "wait": {"action": "wait"},
    "done": {"action": "done"}, "fail": {"action": "fail"},
}
for v in OK.values():
    v.update(say="ok", reason="r")


@pytest.mark.parametrize("name", OK)
def test_valid(name):
    assert validate(OK[name], EL, AL) == (OK[name], None)


def bad(**kw):
    o = copy.deepcopy(OK["tap"])
    for k, v in kw.items():
        o.pop(k, None) if v is None else o.update({k: v})
    return o


@pytest.mark.parametrize("obj", [
    "tap", None, [],
    bad(action="fly"), bad(action=None),
    bad(say=None), bad(say=""), bad(say="x" * 121), bad(reason=None), bad(reason="  "),
    bad(element_id=None), bad(element_id=3), bad(element_id=-1), bad(element_id="1"), bad(element_id=True),
    bad(extra=1), bad(sensitive="yes"),
    {**OK["type"], "text": ""}, {**OK["type"], "text": 5}, {k: v for k, v in OK["type"].items() if k != "text"},
    {**OK["swipe"], "direction": "diagonal"}, {k: v for k, v in OK["swipe"].items() if k != "direction"},
    {**OK["open_app"], "app": "com.phonepe.app"}, {k: v for k, v in OK["open_app"].items() if k != "app"},
])
def test_invalid(obj):
    assert validate(obj, EL, AL)[1] is not None


def test_repeat():
    from src.actions import validate
    base = {"action": "swipe", "direction": "up", "element_id": 0, "say": "s", "reason": "r"}
    els = [{}]
    assert validate({**base, "repeat": 3}, els, set())[1] is None
    for bad in (0, 13, True, "3"):
        assert validate({**base, "repeat": bad}, els, set())[0] is None
    a, err = validate({"action": "back", "say": "s", "reason": "r", "repeat": 2}, els, set())
    assert err is None and "repeat" not in a  # stray repeat on a non-swipe is dropped, not fatal

