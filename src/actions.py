"""Action schema + validate(). Stdlib only; planner/agent import this."""
ACTIONS = {"tap", "type", "swipe", "back", "home", "open_app", "wait", "ask_user", "done", "fail"}
DIRS = {"up", "down", "left", "right"}
OPTIONAL = {"element_id", "text", "direction", "app", "sensitive", "repeat"}
MAX_REPEAT = 12
REQUIRED = {"tap": {"element_id"}, "type": {"element_id", "text"}, "swipe": {"direction"},
            "open_app": {"app"}, "ask_user": set()}  # ask_user's `say` is required for all
SAY_MAX = 120


def validate(obj, elements, allowlist):
    """Return (action_dict, None) or (None, error_string). elements = screen.compact() list."""
    if not isinstance(obj, dict):
        return None, "action must be an object"
    extra = set(obj) - OPTIONAL - {"action", "say", "reason"}
    if extra:
        return None, f"unknown keys: {sorted(extra)}"
    a = obj.get("action")
    if a not in ACTIONS:
        return None, f"action must be one of {sorted(ACTIONS)}"
    for k in ("say", "reason"):
        if not isinstance(obj.get(k), str) or not obj[k].strip():
            return None, f"{k} is required (non-empty string)"
    if len(obj["say"]) > SAY_MAX:
        return None, f"say longer than {SAY_MAX} chars"
    for k in REQUIRED.get(a, ()):
        if k not in obj:
            return None, f"{a} requires {k}"
    if "element_id" in obj:
        i = obj["element_id"]
        if isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < len(elements):
            return None, "element_id not on screen"
    if "text" in obj and (not isinstance(obj["text"], str) or not obj["text"]):
        return None, "text must be a non-empty string"
    if "direction" in obj and obj["direction"] not in DIRS:
        return None, f"direction must be one of {sorted(DIRS)}"
    if "app" in obj and obj["app"] not in allowlist:
        return None, "app not in allowlist"
    if "repeat" in obj and a != "swipe":  # harmless stray field: drop it (eval Nov 6: rejecting it failed 2 runs)
        obj = {k: v for k, v in obj.items() if k != "repeat"}
    if "repeat" in obj and (isinstance(obj["repeat"], bool) or not isinstance(obj["repeat"], int)
                            or not 1 <= obj["repeat"] <= MAX_REPEAT):
        return None, f"repeat must be int 1..{MAX_REPEAT}"
    if "sensitive" in obj and not isinstance(obj["sensitive"], bool):
        return None, "sensitive must be bool"
    return obj, None
