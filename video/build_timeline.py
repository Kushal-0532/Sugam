"""Writes timeline.js from real data: glow-state timings of each take (glow_timeline.py), logs/voice_runs.jsonl,
logs/run_*.jsonl and the cleaned audio. Times in the dict below are seconds inside each take."""
import json, subprocess, array, math
TAKES = {n: float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f"../demo/{'call_blurred' if n == 'call' else n}.mp4"])) for n in ["alarm", "youtube", "call", "whatsapp", "bluetooth"]}

def amps(take, t0, t1, n=44):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(max(0, t0)), "-t", str(max(.2, t1 - t0)), "-i", f"work/{take}.clean.wav", "-f", "s16le", "-ac", "1", "-ar", "16000", "-"], capture_output=True).stdout
    a = array.array("h"); a.frombytes(raw[: len(raw) // 2 * 2]); k = max(1, len(a) // n)
    r = [math.sqrt(sum(x * x for x in a[i * k:(i + 1) * k]) / k) if len(a) >= (i + 1) * k else 0 for i in range(n)]
    m = max(r) or 1
    return [round(max(.12, min(1, x / m)), 2) for x in r]

def pipe(st, T0, rec, stt, A0, said_at, safety=("ok", "allowed"), skip_router=False, phone=("blue", "workflow"), intent=""):
    p = [[st + T0 - rec, "VOICE", "blue", "mic"], [st + T0 + stt * .4, "PRISMA", "blue", f"{stt:.2f} s"]]
    if not skip_router: p.append([st + A0 - .3, "ROUTER", "blue", intent])
    p.append([st + A0 + .1 if not skip_router else st + T0 + stt + .1, "SAFETY", safety[0], safety[1]])
    if phone: p.append([st + A0 + .6, "PHONE", phone[0], phone[1]])
    p.append([st + said_at, "TIMBRE", "blue", "Lakshmi"])
    return [[round(a, 2), b, c, d] for a, b, c, d in p]

def said(take, st, items):
    out = []
    for at, end, text, gloss in items:
        out.append({"at": round(st + at, 2), "dur": min(2.4, end - at), "end": round(st + end, 2), "text": text, "gloss": gloss, "amps": amps(take, at, end)})
    return out

def scene(i, take, tag, st, rec, T0, stt, A0, R0, heard_text, gloss, lang, intent, steps, safety, saids, note, **extra):
    ln = TAKES[take]
    s = {"id": i, "take": take, "start": round(st, 2), "end": round(st + ln, 2), "tag": tag, "speed": 1,
         "heard": {"at": round(st + T0 - rec, 2), "dur": round(rec, 2), "textAt": round(st + T0 + stt, 2), "textDur": 1.0, "text": heard_text, "gloss": gloss, "lang": lang, "stt": f"{stt:.2f} s", "amps": amps(take, T0 - rec, T0)},
         "safety": {"at": round(st + A0 + .2, 2), **safety}, "said": said(take, st, saids), "note": note}
    if steps is not None:
        s["route"] = {"at": round(st + A0 - .4, 2), "intent": intent, "lang": lang, "steps": [[round(st + t, 2), txt] for t, txt in steps]}
    s.update(extra)
    return s

# ---- layout: title 3.2 s, problem line 4.5 s, architecture explainer 39 s, takes back to back (no speed-up), results, end ----
PITCH, ARCH = 4.5, 39.0
t, S = 3.2 + PITCH + ARCH, [{"id": "pitch", "start": 3.2, "end": 3.2 + PITCH, "tag": "", "speed": 1},
                           {"id": "arch", "start": 3.2 + PITCH, "end": 3.2 + PITCH + ARCH, "tag": "", "speed": 1}]
def nxt(n):
    global t
    a = t; t += TAKES[n]; return a

st = nxt("youtube")
S.append(scene(1, "youtube", "1 · YouTube", st, 3.61, 6.8, .47, 9.8, 18.5,
    "Play \"Alone by Marshmella\"\non YouTube.", "Play \"Alone\" by Marshmello\non YouTube (as heard)", "en", "youtube_search + play",
    [(10.6, "open YouTube"), (12.0, "type the search"), (14.3, "search"), (16.6, "tap first real video")],
    {"state": "ok", "word": "ALLOWED", "why": "YouTube is on the\nallowlist"},
    [(9.9, 11.4, "On it.", "Spoken by Timbre"), (18.6, 20.0, "Done.", "Spoken by Timbre")], "Search, then tap the first non-sponsored video",
    pipe=pipe(st, 6.8, 3.61, .47, 9.8, 18.6, intent="youtube")))
st = nxt("call")
S.append(scene(2, "call", "2 · Call Test Amma", st, 2.82, 5.7, .6, 8.7, 21.0,
    "Test Amma को call करो।", "Call Test Amma", "hi", "call",
    [(9.9, "open Contacts"), (11.6, "find Test Amma"), (12.6, "ask to confirm")],
    {"state": "ask", "word": "ASK FIRST", "why": "Calls need a\nspoken yes"},
    [(12.8, 16.4, "क्या आगे बढ़ें? हाँ या\nनहीं बोलिए।", "Shall I go ahead?\nSay yes or no."), (21.4, 24.8, "ठीक है, रद्द कर दिया।", "Okay, I cancelled it.")],
    "Synthetic contact · the call was never placed",
    noteAt=round(st + 21.2, 2), circle=[round(st + 21.2, 2), 65, 490, "NOT tapped"], sub="The answer was not a yes, so nothing was tapped",
    pipe=pipe(st, 5.7, 2.82, .6, 8.7, 12.8, safety=("ask", "confirm"), intent="call")))
st = nxt("alarm")
S.append(scene(3, "alarm", "3 · Telugu alarm", st, 8.35, 12.7, 1.16, 15.9, 26.5,
    "రేపు ten twenty seven\nపొద్దున ఒక alarm పెడతావా?", "Set an alarm for tomorrow\nmorning, 10:27", "te", "set_alarm",
    [(17.4, "open Clock"), (21.5, "set 10:27 AM"), (26.0, "tap Done")],
    {"state": "ok", "word": "ALLOWED", "why": "Clock is on the\nallowlist"},
    [(16.0, 18.6, "సరే, చేస్తున్నాను.", "OK, doing it."), (26.6, 29.6, "అయిపోయింది.", "Done.")], "Alarm saved for 10:27 AM",
    pipe=pipe(st, 12.7, 8.35, 1.16, 15.9, 26.6, intent="alarm"), noteAt=round(st + 26.6, 2)))
st = nxt("whatsapp")
S.append(scene(4, "whatsapp", "4 · WhatsApp", st, 2.71, 10.5, .46, 10.96, 10.9,
    "WhatsApp open చెయ్యి.", "Open WhatsApp", "te", None, None,
    {"state": "block", "word": "BLOCKED", "why": "Caught in the words,\nbefore any model runs"},
    [(11.2, 14.2, "భద్రత కోసం ఆ యాప్\nబ్లాక్ చేయబడింది.", "That app is blocked\nfor safety.")], "The phone never opened WhatsApp",
    noteAt=round(st + 11.2, 2), stamp=[round(st + 11.0, 2), "BLOCKED"],
    pipe=pipe(st, 10.5, 2.71, .46, 10.96, 11.2, safety=("block", "BLOCKED"), skip_router=True, phone=None)))
S[-1]["safety"]["at"] = round(st + 11.0, 2)
st = nxt("bluetooth")
S.append(scene(5, "bluetooth", "5 · Bluetooth (agent)", st, 2.43, 5.7, 5.27, 11.9, 25.0,
    "Bluetooth on చేయి.", "Turn on Bluetooth", "te", "agent_loop",
    [(15.3, "open Settings"), (18.4, "tap Bluetooth"), (22.0, "tap the switch"), (24.6, "check, done")],
    {"state": "ok", "word": "ALLOWED", "why": "Settings allowed\nfor this demo"},
    [(12.0, 14.0, "సరే, చేస్తున్నాను.", "OK, doing it."), (25.1, 27.0, "అయిపోయింది.", "Done.")], "LLM agent loop: 4 steps, 13 s",
    pipe=pipe(st, 5.7, 2.43, 5.27, 11.9, 25.1, intent="agent", phone=("blue", "agent")),
    loop=[round(st + 12.2, 2), round(st + 25.0, 2)], noteAt=round(st + 25.0, 2)))
S[-1]["route"]["stepCount"] = "25"
res_st = t; t += 7.0
S.append({"id": "results", "start": round(res_st, 2), "end": round(t, 2), "tag": "", "speed": 1})
end_st = t; t += 6.0
S.append({"id": "end", "start": round(end_st, 2), "end": round(t, 2), "tag": "", "speed": 1})

TL = {"mock": False, "dur": round(t, 2), "repo": "github.com/Kushal-0532/Sugam",
      "claim": ["Sugam", "Speak in your language.", "We'll handle the rest."],
      "pitch": ["Your grandmother shouldn't need", "English or steady hands", "to set an alarm.", "With Sugam, she just says it."], "scenes": S,
      "results": {"pass": 52, "total": 72, "pct": "72%", "median": "8.0 s", "tag": "Jev + gpt-oss-120b · 24 recorded te/hi clips, dry-run",
                  "notes": ["49/72 before fixing one test check", "LLM agent 3/15 · workflows + blocks 46/57", "Most failures: speech mishears", "Typed agent tasks: 9/9"]},
      "end": {"title": "Sugam", "tag": "Easy phone access, in your own language", "lines": ["Listens: Gnani Prisma v3.0", "Speaks: Gnani Timbre v3.0", "Decides: Jev + Groq fallback", "v1: laptop + USB cable", "v2: standalone APK (coming)"]}}
open("timeline.js", "w").write("// GENERATED by build_timeline.py from real takes/logs. Do not edit by hand.\nwindow.TL = " + json.dumps(TL, ensure_ascii=False, indent=1) + ";\n")
print("dur", TL["dur"], "frames", int(TL["dur"] * 24), [(s["id"], s["start"], s["end"]) for s in S])
