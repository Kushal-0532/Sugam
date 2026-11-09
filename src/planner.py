"""LLM planner: OpenAI-compatible adapter (Groq, model from LLM_MODEL). Anthropic adapter not built yet."""
import json, os, re, time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError
from .actions import ACTIONS, DIRS, validate
from .safety import TEST_CONTACTS

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env"); load_dotenv(ROOT / ".env.example"); load_dotenv(Path.home() / ".env")  # .env.example = non-secret defaults

TOOL = {"type": "function", "function": {"name": "act", "description": "Perform one UI action.", "parameters": {
    "type": "object", "additionalProperties": False,
    "required": ["action", "say", "reason"],
    "properties": {
        "action": {"type": "string", "enum": sorted(ACTIONS)},
        "element_id": {"type": "integer"}, "text": {"type": "string"},
        "direction": {"type": "string", "enum": sorted(DIRS)}, "repeat": {"type": "integer"}, "app": {"type": "string"},
        "say": {"type": "string"}, "sensitive": {"type": "boolean"}, "reason": {"type": "string"}}}}}


class RateLimited(RuntimeError):
    """LLM quota exhausted (e.g. Groq free tier: 200k tokens/day, refills ~2.3 tokens/s). Not an agent failure."""


def script_lang(text):
    return "te" if any("\u0c00" <= c <= "\u0c7f" for c in text) else "hi" if any("\u0900" <= c <= "\u097f" for c in text) else "en"


def view(elements):
    """One line per element: id|label|flags. ~3x fewer tokens than JSON; cx/cy are not needed by the LLM."""
    out = []
    for e in elements:
        label = (e["text"] or e["desc"]).replace("\n", " ")[:60]
        flags = ("C" if e["click"] else "") + ("E" if e["edit"] else "") + ("S" if e["scroll"] else "")
        out.append(f"{e['id']}|{label or '#' + e['rid']}|{flags}")
    return "\n".join(out)


def _client():
    return OpenAI(base_url=os.environ["LLM_BASE_URL"], api_key=os.environ[os.environ["LLM_API_KEY_VAR"]], max_retries=0)  # we handle 429 ourselves


def _call(messages):
    for wait in (2, 5, None):  # ponytail: fixed backoff on 429; read retry-after if TPM stalls persist
        try:
            return _call_once(messages)
        except RateLimitError:
            if wait is None:
                raise
            time.sleep(wait)


def _call_once(messages):
    r = _client().chat.completions.create(
        model=os.environ["LLM_MODEL"], messages=messages, tools=[TOOL],
        tool_choice={"type": "function", "function": {"name": "act"}}, temperature=0,
        **({"reasoning_effort": os.environ["LLM_REASONING"]} if os.environ.get("LLM_REASONING") else {}))
    return json.loads(r.choices[0].message.tool_calls[0].function.arguments)


def next_action(goal, lang, elements, history, allowlist):
    """-> (action, None) or (None, err). One re-ask on invalid output."""
    apps = {k: v["pkg"] for k, v in allowlist.items()}
    sys = (ROOT / "prompts/planner.md").read_text() + f"\nALLOWED APPS: {json.dumps(apps)}\nLANG: {lang}"
    user = f"GOAL: {goal}\nLAST ACTIONS: {json.dumps(history[-4:], ensure_ascii=False, separators=(',', ':'))}\nSCREEN:\n{view(elements)}"
    msgs = [{"role": "system", "content": sys}, {"role": "user", "content": user}]
    pkgs = set(apps.values())
    err = None
    for _ in range(2):
        try:
            a, err = validate(_call(msgs), elements, pkgs)
        except RateLimitError as e:
            raise RateLimited(str(e)[:300])
        except Exception as e:
            a, err = None, f"llm error: {e}"
            time.sleep(1.5)  # 400 tool_use_failed is transient: wait before the re-ask
        if a:
            return a, None
        msgs.append({"role": "user", "content": f"Invalid action: {err}. Try again."})
    return None, err


ROUTE_TASKS = ("alarm", "timer", "youtube_search", "maps_search", "chrome_search", "wifi_settings", "call", "message", "spotify_play", "agent")
ROUTE_TOOL = {"type": "function", "function": {"name": "route", "description": "Classify the user's request.", "parameters": {
    "type": "object", "additionalProperties": False, "required": ["task", "lang", "goal"],
    "properties": {
        "task": {"type": "string", "enum": list(ROUTE_TASKS)},
        "hour": {"type": "integer", "description": "REQUIRED when task=alarm: hour in 24h clock 0-23 (7 am=7, 6:30 pm=18)"},
        "minute": {"type": "integer", "description": "REQUIRED when task=alarm: 0-59 (0 if not said)"},
        "minutes": {"type": "integer", "description": "REQUIRED when task=timer: total minutes (1 hour = 60)"},
        "seconds": {"type": "integer", "description": "task=timer: extra seconds 0-59 (0 if not said)"},
        "contact": {"type": "string", "description": "REQUIRED when task=call/message: the contact name in Latin letters as saved in the phone (e.g. 'Test అమ్మ' -> 'Test Amma'); copy what was said, never guess a different name"},
        "text": {"type": "string", "description": "REQUIRED when task=message: the message body in the user's own words and script, as the sender would write it (first person)"},
        "query": {"type": "string", "description": "search text copied EXACTLY as the user said it, same words and same script; never translate or transliterate (Telugu stays Telugu, Hindi stays Devanagari)"},
        "artist": {"type": "string", "description": "task=spotify_play: the artist if said, else empty string; query = the song title only"},
        "lang": {"type": "string", "enum": ["te", "hi", "hinglish", "en"]},
        "goal": {"type": "string", "description": "the request in plain English"}}}}}
ROUTE_SYS = ("Classify a phone voice command (Telugu/Hindi/Hinglish/English). task=alarm only for setting ONE alarm at a "
             "clear time: you MUST fill hour (0-23) and minute (0-59) for every alarm, e.g. 'evening 6' -> hour 18 minute 0. "
             "task=timer only for ONE countdown with a stated duration (fill minutes). task=call / message for calling or "
             "texting ONE named contact (fill contact; message also text). task=wifi_settings to open the Wi-Fi settings page. "
             "task=youtube_search / maps_search / chrome_search (web search in Chrome/Google) only for plain "
             "search/find requests in that app; query = the search words copied verbatim from the user in their original script "
             "(drop only the app name and the verb, e.g. 'హైదరాబాద్ ఎయిర్‌పోర్ట్ మ్యాప్స్ లో వెతుకు' -> 'హైదరాబాద్ ఎయిర్‌పోర్ట్'). "
             "task=spotify_play to play ONE named song on Spotify: query = song title, artist = artist if said (else empty); play-by-genre or playlists = agent. "
             "lang: te=Telugu script, hi=Devanagari, hinglish=Hindi written in Latin letters, en=English. Anything else, ambiguous, or multi-step = agent. Always call `route`.")


# Qwen at reasoning=none omits required fields unless told exactly (Nov 6: missing task/lang/goal, missing message text).
PIN_FIELDS = {"alarm": "hour and minute", "timer": "minutes and seconds", "youtube_search": "query", "maps_search": "query",
              "chrome_search": "query", "spotify_play": "query (song title) and artist", "call": "contact", "message": "contact and text (the message body)"}


def understand(transcript, task=None):
    """One short LLM call: transcript -> {task, lang, goal, hour?, minute?, query?, ...}. Falls back to agent.
    task = already decided (by Jev): the LLM only fills in that task's details."""
    system = ROUTE_SYS + (f" The task is already decided: task={task}. Call `route` with task, lang, goal and also "
                          f"{PIN_FIELDS.get(task, 'nothing else')}." if task else "")
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": transcript}]
    for wait in (2, 5, None):
        try:
            r = _client().chat.completions.create(
                model=os.environ["LLM_MODEL"], messages=msgs, tools=[ROUTE_TOOL], temperature=0,
                tool_choice={"type": "function", "function": {"name": "route"}},
                **({"reasoning_effort": os.environ["LLM_REASONING"]} if os.environ.get("LLM_REASONING") else {}))
            d = json.loads(r.choices[0].message.tool_calls[0].function.arguments)
            if task and isinstance(d, dict):
                d["task"] = task
            return check_route(d, transcript)
        except RateLimitError as e:
            if wait is None:
                raise RateLimited(str(e)[:300])
            time.sleep(wait)
        except Exception as e:  # Qwen sometimes fails forced tool calls (HTTP 400 tool_use_failed): worth a retry
            print(f"router call failed: {str(e)[:160]}")
            if wait is None:
                break
    return {"task": "agent", "lang": "en", "goal": transcript}


# ponytail: keyword heuristic for multi-step requests; a false positive only costs a slower agent run.
_SEARCH = r"(search|find|look (?:up|for)|సెర్చ్|వెతి|खोज|ढूंढ|सर्च|khoj|dh[ou]+n?dh)"
_JOIN = r"(\band\b|\bthen\b|,|&|తర్వాత|చేసి|వెతికి|और|फिर|करके|\baur\b|\bphir\b|karke|kar ke)"
_NEXT = r"(play|watch|open|tap|click|select|choose|subscribe|like|save|share|scroll|filter|sort|ప్లే|చూడు|తెరు|ఓపెన్|चलाओ|देखो|खोलो|प्ले|chalao|dekho|kholo)"
_MORE = re.compile(rf"{_SEARCH}.*?{_JOIN}.*?{_NEXT}|\b(scroll|channel|subscribe|sort by|go to)\b|ఛానల్|चैनल|स्क्रॉल", re.I)


def beyond_search(transcript):
    """True when the request needs more than a search handler does (those would drop the rest and still report done)."""
    return bool(_MORE.search(transcript))


# ponytail: same idea for alarm/timer/wifi: action verb, join, another action. "open" excluded ("open clock and set alarm" is one task).
_ACT = r"(play|watch|set|start|turn|put|call|text|send|message|remind|ప్లే|పెట్టు|చూడు|చెయ్యి|चलाओ|लगाओ|देखो|प्ले|chalao|lagao|dekho)"
_COMPOUND = re.compile(rf"{_ACT}.*?{_JOIN}.*?{_ACT}", re.I)


def compound(transcript):
    """True when a one-task handler request also asks for another action (the handler would drop it and report done)."""
    return bool(_COMPOUND.search(transcript))


_PLAY = re.compile(r"\b(play|watch|chalao|chala|dekho)\b|ప్లే|చూడు|चलाओ|प्ले|देखो", re.I)


# ponytail: the one-song handler matches a song TITLE, so an album/playlist request would play a same-named song (Nov 9: gpt-oss router
# played "Random Access Memories" by Dreaming Diary). Keyword guard, any router.
_COLLECTION = re.compile(r"\b(album|albums|playlist|playlists|liked songs|mix)\b|ఆల్బమ్|ప్లేలిస్ట్|एल्बम|एलबम|प्लेलिस्ट", re.I)


def check_route(d, transcript):
    """Deterministic guard: any malformed/underspecified route degrades to the agent loop (never guess a time)."""
    ok = isinstance(d, dict) and d.get("task") in ROUTE_TASKS
    if ok and d["task"] == "alarm":
        h, m = d.get("hour"), d.get("minute", 0)
        ok = all(isinstance(x, int) and not isinstance(x, bool) for x in (h, m)) and 0 <= h <= 23 and 0 <= m <= 59
    if ok and d["task"] in ("youtube_search", "maps_search", "chrome_search", "spotify_play"):
        ok = isinstance(d.get("query"), str) and bool(d["query"].strip())
        if ok and (beyond_search(transcript) or (d["task"] == "spotify_play" and _COLLECTION.search(transcript))):
            return {"task": "agent", "lang": script_lang(transcript), "goal": transcript}
    if ok and d["task"] == "timer":
        mi, s = d.get("minutes"), d.get("seconds", 0)
        ok = all(isinstance(x, int) and not isinstance(x, bool) for x in (mi, s)) and 0 <= s <= 59 and 0 < mi * 60 + s < 24 * 3600
    if isinstance(d, dict) and d.get("task") in ("call", "message"):
        # never falls back to the agent loop: that would put real contacts in front of the LLM
        if d.get("contact") not in TEST_CONTACTS or (d["task"] == "message" and not str(d.get("text") or "").strip()):
            return {"task": "blocked_contact", "lang": d.get("lang", "en"), "goal": transcript, "contact": d.get("contact")}
    if ok and d["task"] in ("alarm", "timer", "wifi_settings", "spotify_play") and compound(transcript):
        return {"task": "agent", "lang": script_lang(transcript), "goal": transcript}
    if not ok:
        return {"task": "agent", "lang": "en", "goal": transcript}
    if d["task"] == "youtube_search":
        d["play"] = bool(_PLAY.search(transcript))  # "play X on YouTube" = search + tap the first video
    d.setdefault("lang", "en")
    if script_lang(transcript) != "en":  # the script decides the reply language, not the model (Qwen: Devanagari -> hinglish)
        d["lang"] = script_lang(transcript)
    g = d.get("goal")
    if not isinstance(g, str) or len(g.strip()) < 6 or g.strip().lower() in ROUTE_TASKS:  # model sometimes echoes the task name
        d["goal"] = transcript
    return d
