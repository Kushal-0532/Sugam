"""Jev (TypeSafe's typed-decision model) via OpenRouter's /api/v1/systemone. Jev picks from options we give it and
returns {choice, confidence, probabilities}; it never writes text. Groq (planner.py) covers text and low confidence.
Measured Nov 6 on the clock fixture: 0.46 s median vs Groq 0.68-0.87 s, both 10/10 correct (en + te goal)."""
import os, time
from pathlib import Path
import requests
from dotenv import load_dotenv
from .actions import validate

load_dotenv(Path.home() / ".env")
URL = "https://openrouter.ai/api/v1/systemone"
MODEL = os.environ.get("JEV_MODEL", "typesafe/jev-1.14")
ROUTE_MIN, STEP_MIN = 0.8, 0.6  # confidence thresholds (user-approved Nov 6; tune on eval data)
REACH_MIN = 0.7  # ponytail: uncalibrated guess for the step checkpoint; tune once runs reach it


def ask(state, questions, timeout=10):
    """-> ({name: answer}, seconds). One retry on 429/5xx; raises on anything else."""
    h = {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "Content-Type": "application/json"}
    t = time.time()
    for wait in (1, None):
        r = requests.post(URL, headers=h, json={"model": MODEL, "state": state, "questions": questions}, timeout=timeout)
        if r.ok or wait is None or (r.status_code != 429 and r.status_code < 500):
            break
        time.sleep(wait)
    r.raise_for_status()
    return r.json()["answers"], round(time.time() - t, 2)


TASKS = {"alarm": "set one alarm at a stated time", "timer": "start one countdown timer for a stated duration",
         "youtube_search": "search for something on YouTube", "maps_search": "find a place on Google Maps",
         "chrome_search": "search the web in Chrome or Google", "wifi_settings": "open the Wi-Fi settings page",
         "call": "phone call to a contact", "message": "send a text message to a contact",
         "spotify_play": "play one named song on Spotify", "open_app": "only open an app, nothing else", "agent": "anything else, several steps, or unclear"}


def route(transcript, allowlist):
    """Router extra: -> ({task, conf, app, app_conf}, seconds). Only no-detail tasks may skip Groq (agent.run_routed)."""
    apps = {k: f"the {k} app ({', '.join(map(str, v.get('aliases', [])))})" for k, v in allowlist.items()}
    a, s = ask(f"A user said this to their phone (Telugu, Hindi, English or a mix): {transcript}", {
        "task": {"type": "choice", "instructions": "What does the user want the phone to do?", "criteria": TASKS},
        "app": {"type": "choice", "instructions": "If the user only wants an app opened, which app?", "criteria": apps}})
    return {"task": a["task"]["choice"], "conf": a["task"]["confidence"],
            "app": a["app"]["choice"], "app_conf": a["app"]["confidence"]}, s


def reachable(goal, elements, history):
    """Checkpoint question. -> (probability the goal is reached within 5 more steps, seconds)."""
    import json
    from .planner import view
    a, s = ask(f"GOAL (user's own words): {goal}\nLAST ACTIONS: {json.dumps(history[-6:], ensure_ascii=False)}\n"
               f"SCREEN (id|label|flags, C=clickable E=editable S=scrollable):\n{view(elements)}",
               {"reach": {"type": "noul", "instructions": "Will the goal be fully reached within the next 5 steps?"}})
    return a["reach"]["noul"], s


STEP_ACTIONS = {"tap": "tap one on-screen element (button, tab, key, list item)", "type": "enter text into a text field",
                "swipe_up": "scroll to reveal content further down (swipe up)", "swipe_down": "scroll back up (swipe down)",
                "back": "go back to the previous screen", "open_app": "launch an app that is not on screen yet",
                "done": "the goal is already achieved and visible on screen", "fail": "the goal cannot be reached from here"}


def step(goal, elements, history, allowlist, phrase, force=False):
    """Agent-loop step. -> (action|None, info). action None = hand this step to Groq (info['why'] says why).
    phrase(key) gives the fixed narration in the user's language (Jev writes no text)."""
    import json
    from .planner import view
    els = {str(e["id"]): (e["text"] or e["desc"] or e["rid"] or e["cls"])[:80] for e in elements
           if e["click"] or e["edit"] or e["scroll"]}
    apps = {k: f"the {k} app" for k in allowlist}
    state = (f"GOAL (user's own words): {goal}\nLAST ACTIONS: {json.dumps(history[-4:], ensure_ascii=False)}\n"
             f"SCREEN (id|label|flags, C=clickable E=editable S=scrollable):\n{view(elements)}")
    q = {"action": {"type": "choice", "criteria": STEP_ACTIONS, "instructions":
                    "Given the goal, the actions already taken and the current screen, what is the ONE next step?"},
         "app": {"type": "choice", "criteria": apps, "instructions": "If an app must be opened next, which one?"},
         "outward": {"type": "noul", "instructions": "Would the next step toward this goal send a message, place a call, "
                                                     "pay, delete, or post something?"}}
    if els:
        q["element"] = {"type": "choice", "criteria": els, "instructions":
                        "Which on-screen element should the next tap, text entry or scroll act on?"}
    try:
        a, s = ask(state, q)
    except Exception as e:
        return None, {"why": f"jev error: {e}"[:120]}
    act, conf = a["action"]["choice"], a["action"]["confidence"]
    el = a.get("element", {})
    info = {"jev_s": s, "action": act, "conf": conf, "element": el.get("choice"), "el_conf": el.get("confidence"),
            "outward": a["outward"]["noul"]}
    if act == "type":
        return None, {**info, "why": "text needed"}
    if act == "fail":
        return None, {**info, "why": "jev says fail; groq gets one try"}
    if conf < STEP_MIN and not force:  # force: Groq failed, take Jev's best guess
        return None, {**info, "why": f"low action confidence {conf}"}
    if act == "tap" and (not el or (el["confidence"] < STEP_MIN and not force)):
        return None, {**info, "why": f"low element confidence {el.get('confidence')}"}
    say = phrase("done" if act == "done" else "working")
    reason = f"jev {act} conf {conf}"
    obj = {"tap": lambda: {"action": "tap", "element_id": int(el["choice"])},
           "swipe_up": lambda: {"action": "swipe", "direction": "up"},
           "swipe_down": lambda: {"action": "swipe", "direction": "down"},
           "back": lambda: {"action": "back"},
           "open_app": lambda: {"action": "open_app", "app": allowlist[a["app"]["choice"]]["pkg"]},
           "done": lambda: {"action": "done"}}[act]()
    if obj["action"] == "swipe" and el and elements[int(el["choice"])]["scroll"]:  # scroll inside the list Jev named
        obj["element_id"] = int(el["choice"])
    v, err = validate({**obj, "say": say, "reason": reason}, elements, {x["pkg"] for x in allowlist.values()})
    return (v, info) if v else (None, {**info, "why": f"invalid jev pick: {err}"})
