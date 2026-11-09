"""Agent eval on the real phone. Input = the user's recorded clips, transcribed ONCE by stt_eval.py
(eval/transcripts.json); each transcript is replayed --n times through agent.run_routed (router -> handler or agent
loop), narration off, dry-run per tasks.yaml. Success is decided here, on the live screen, not by the agent's outcome.
Private apps (contacts/messages/settings/chrome) are checked with selectors only: no dumps, no screenshots.

  python eval/run_eval.py --n 3 --tag before [--only alarm_7am,wifi]"""
import argparse, csv, json, os, re, statistics, subprocess, sys, time
from pathlib import Path
from urllib.parse import unquote_plus
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import agent, handlers as H, phone  # noqa: E402

CALC, YT, MAPS = "com.oneplus.calculator", H.YT, H.MAPS
APPS = [H.CLOCK, YT, MAPS, CALC, H.SETTINGS, H.WIRELESS, H.CHROME, H.CONTACTS, H.MSGS]


def has(text, *words):
    return bool(text) and bool(re.search("|".join(words), text, re.I))


def pickers_are(d, want):
    ps = H._pickers(d)
    return (H._vals(ps) == want) if ps else False, f"pickers {H._vals(ps) if ps else None}"


def yt(d, out):
    # Nov 9: "play ..." commands now tap the first video (handlers.youtube_search play=True), so the run ends on the player,
    # not the results page. A open player on a play request counts as a pass (the handler already verified watch_player).
    if d(resourceId=YT + ":id/watch_player").exists:
        return True, "yt player open (play request)"
    q = d(resourceId=YT + ":id/search_query")
    t = q.get_text() if q.exists else ""
    return has(t, "devotional", "bhakti", "భక్తి", "भक्ति", "bhajan", "భజన", "भजन"), f"yt query {t!r}"


def maps(*words):
    def check(d, out):
        b = d(resourceId=MAPS + ":id/search_omnibox_text_box")
        t = " ".join(filter(None, (b.info.get("text"), b.info.get("contentDescription")))) if b.exists else ""
        return has(t, *words), f"maps box {t!r}"
    return check


def chrome(d, out):
    b = d(resourceId=H.CHROME + ":id/url_bar")
    t = unquote_plus(b.get_text() or "") if b.exists else ""
    ok = has(t, "weather", "వాతావరణ", "मौसम")
    return ok, "url has weather query" if ok else "url bar lacks a weather query"  # never print the URL (private app)


def contact_card(d, out):
    ok = out == "dry_run_ok" and d(className="android.widget.TextView", text="Test Amma").exists \
        and d(className="android.widget.Button", description="Call").exists
    return ok, f"outcome {out}, card+Call {'shown' if ok else 'not shown'}"


def draft(d, out):
    b = d(resourceId=H.MSGS + ":id/compose_message_text")
    t = b.get_text() if b.exists else ""
    ok = out == "dry_run_ok" and d(text="Test Papa").exists and has(t, "खाना", "खा", "తిన్న", "తిన", "khana", "ate")
    return ok, f"outcome {out}, draft {'ok' if ok else 'missing/wrong'}"


PRED = {
    "alarm_7am": lambda d, out: pickers_are(d, [7, 0, 0]),
    "alarm_630pm": lambda d, out: pickers_are(d, [6, 30, 1]),
    "timer_5min": lambda d, out: pickers_are(d, [0, 5, 0]),
    "calculator": lambda d, out: (phone.snapshot(d)[2] == CALC, f"foreground {phone.snapshot(d)[2]}"),
    "wifi": lambda d, out: (d(text="Wi‑Fi").exists and d(className="android.widget.Switch").exists, "wifi page check"),
    "chrome_weather": chrome,
    "youtube_devotional": yt,
    "maps_hospital": maps("hospital", "ఆసుపత్రి", "హాస్పిటల్", "अस्पताल", "हॉस्पिटल"),
    "maps_pharmacy": maps("pharmac", "medical", "ఫార్మసీ", "మెడికల్", "मेडिकल", "फार्मेसी", "दवा"),
    "call_amma": contact_card,
    "msg_papa": draft,
    "paytm_block": lambda d, out: (out == "denied_app", f"outcome {out}"),
}


# Forced through the agent loop (typed text, not clips): safe apps only, all steps are planner decisions.
AGENT_SET = {
    "calc_12x8": ("calculate 12 times 8 on the calculator", lambda d, out: (
        d(resourceId=CALC + ":id/result").exists and d(resourceId=CALC + ":id/result").get_text() == "96", "result field")),
    "world_clock": ("క్లాక్ యాప్‌లో world clock చూపించు", lambda d, out: (
        d(resourceId=H.CLOCK + ":id/clock").exists and d(resourceId=H.CLOCK + ":id/clock").info.get("selected"), "world clock tab selected")),
    "timer_tab": ("क्लॉक ऐप में टाइमर खोलो", lambda d, out: (bool(H._pickers(d)), "timer pickers on screen")),
}


def reset(d):
    """Precondition: home, every eval app stopped, no leftover draft or running timer."""
    d.press("home")
    for p in APPS:
        d.app_stop(p)
    time.sleep(0.5)


def precondition(d, tid):
    """The calculator restores its last sum after a force-stop (12x8=96 would be an instant false pass, seen Nov 6), and
    Clear only sticks if the app is NOT stopped afterwards. So: open, Clear, go home, leave it running; verify on resume."""
    if tid == "calc_12x8":
        d.app_start(CALC, stop=True)
        c, r = d(resourceId=CALC + ":id/clr"), d(resourceId=CALC + ":id/result")
        if not H._wait(lambda: c.exists, 5):
            raise RuntimeError("precondition: calculator Clear not shown")
        c.click()
        time.sleep(0.5)
        d.press("home")
        time.sleep(0.5)
        d.app_start(CALC)
        time.sleep(1.5)
        if r.exists and r.get_text():
            raise RuntimeError(f"precondition: calculator still shows {r.get_text()!r}")
        d.press("home")
        time.sleep(0.5)


def cleanup(d, tid):
    if tid == "msg_papa":
        b = d(resourceId=H.MSGS + ":id/compose_message_text")
        if b.exists:
            b.clear_text()
    if tid == "timer_5min" and d(description="Reset").exists:  # an agent-loop run may have started the timer
        d(description="Reset").click()
    d.press("home")


def meta():
    g = lambda k: subprocess.run(["adb", "shell", "getprop", k], capture_output=True, text=True).stdout.strip()
    c = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    return {"date": time.strftime("%Y-%m-%d %H:%M"), "phone": g("ro.product.model"), "android": g("ro.build.version.release"),
            "llm": os.environ.get("LLM_MODEL"), "reasoning": os.environ.get("LLM_REASONING"), "commit": c or "uncommitted",
            "planner": os.environ.get("PLANNER", "groq")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--tag", default="run")
    ap.add_argument("--only")
    ap.add_argument("--agent-set", action="store_true", help="force the agent loop on AGENT_SET instead of the clip tasks")
    ap.add_argument("--stt", default="default", choices=["default", "lang"],
                    help="which transcripts: default (te,hi,en auto-detect) or lang (user's language set, @lang)")
    a = ap.parse_args()
    tasks = {k: v for k, v in yaml.safe_load((ROOT / "eval/tasks.yaml").read_text()).items() if v["kind"] == "task"}
    if a.only:
        tasks = {k: v for k, v in tasks.items() if k in a.only.split(",")}
    tr = json.loads((ROOT / "eval/transcripts.json").read_text())
    d = phone.connect()
    rows, m = [], meta()
    if a.agent_set:
        cases = [(tid, "typed", text, pred, True, True) for tid, (text, pred) in AGENT_SET.items() if not a.only or tid in a.only.split(",")]
    else:
        cases = [(tid, lang, tr[f"{tid}_{lang}" + ("@lang" if a.stt == "lang" else "")]["transcript"], PRED[tid], t["dry_run"], False)
                 for tid, t in tasks.items() for lang in ("telugu", "hindi")]
    stopped = None
    try:
        for tid, lang, text, pred, dry, force in cases:
            for i in range(a.n):
                try:
                    reset(d)
                    precondition(d, tid)
                except Exception:  # u2 flakes (RemoteDisconnected): reconnect once; a truly dropped phone ends the eval
                    time.sleep(3)
                    d = phone.connect()
                    reset(d)
                    precondition(d, tid)
                stats, lines, t0 = {}, [], time.time()
                try:
                    out = agent.run_routed(text, dry, say=lines.append, stats=stats, force_agent=force)
                except Exception as e:  # a crash is a result, not a reason to stop the eval
                    out = f"crash: {type(e).__name__}: {e}"[:120]
                wall = round(time.time() - t0, 1)
                for attempt in range(3):  # StaleObjectException: the UI moved between .exists and .info (eval Nov 6)
                    try:
                        ok, why = pred(d, out)
                        ok = bool(ok)  # u2 .exists is an Exists object, not a bool
                        break
                    except Exception as e:
                        ok, why = False, f"predicate error: {e}"[:120]
                        time.sleep(0.5)
                cleanup(d, tid)
                r = {"task": tid, "lang": lang, "run": i, "pass": ok, "route": stats.get("task"), "outcome": out,
                     "why": why, "wall_s": wall, "route_s": stats.get("route_s"), "jev_task": stats.get("jev_task"),
                     "jev_conf": stats.get("jev_conf"), "jev_steps": stats.get("jev_steps", 0), "groq_steps": stats.get("groq_steps", 0),
                     "planner_s": stats.get("planner_s", 0), "transcript": text}
                rows.append(r)
                if out == "llm_rate_limited":  # quota, not a result: drop this run and stop, keep what we have
                    rows.pop()
                    stopped = f"stopped early: LLM rate limit at {tid}_{lang}#{i}"
                    print(stopped, flush=True)
                    return
                print(f"{'PASS' if ok else 'FAIL'} {tid}_{lang}#{i} {wall}s route={r['route']} out={out} "
                      f"steps jev={r['jev_steps']} groq={r['groq_steps']} planner={r['planner_s']}s | {why}", flush=True)
    except Exception as e:  # e.g. phone dropped off USB: keep the finished runs
        stopped = f"stopped early: {type(e).__name__}: {e}"[:200]
        print(stopped, flush=True)
    finally:
        if rows:
            write(rows, {**m, "stt": a.stt, "stopped": stopped}, a.tag, a.n)


def write(rows, m, tag, n):
    out = ROOT / "eval"
    with (out / f"results_{tag}.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    rate = lambda rs: f"{sum(r['pass'] for r in rs)}/{len(rs)} ({100 * sum(r['pass'] for r in rs) / len(rs):.0f}%)" if rs else "-"
    med = lambda rs: f"{statistics.median(r['wall_s'] for r in rs):.1f}" if rs else "-"
    handler = [r for r in rows if r["route"] in H.HANDLERS or r["route"] in ("denied", "blocked_contact")]
    loop = [r for r in rows if r not in handler]
    md = [f"# Agent eval — {tag}", "",
          f"{m['date']} · {m['phone']} (Android {m['android']}) · planner {m['planner']} · LLM {m['llm']} (reasoning {m['reasoning']}) · commit {m['commit']} · "
          f"STT transcripts: {'language set per user (te-IN,en-IN / hi-IN,en-IN)' if m['stt'] == 'lang' else 'default (te,hi,en auto-detect)'}", "",
          *([f"**PARTIAL: {m['stopped']}. Only {len(rows)} runs below.**", ""] if m.get("stopped") else []),
          f"Input: the user's 24 recorded clips (12 commands × Telugu/Hindi), transcribed once by Gnani Prisma "
          f"(`eval/stt_results.md`), each transcript replayed {n}× on the real phone. Success = harness predicate on the "
          f"live screen after the run. Dry-run tasks stop before the commit tap (alarm Done, timer Start, Call, Send); "
          f"sending/calling is disabled entirely (user rule). STT errors are included: a misheard clip counts as a fail.", "",
          f"**Overall: {rate(rows)}** · median wall {med(rows)} s", "",
          "| split | pass | median s |", "|---|---|---|",
          f"| Telugu | {rate([r for r in rows if r['lang'] == 'telugu'])} | {med([r for r in rows if r['lang'] == 'telugu'])} |",
          f"| Hindi | {rate([r for r in rows if r['lang'] == 'hindi'])} | {med([r for r in rows if r['lang'] == 'hindi'])} |",
          f"| routed to a deterministic handler / safety block | {rate(handler)} | {med(handler)} |",
          f"| routed to the LLM agent loop | {rate(loop)} | {med(loop)} |", "",
          "| task | te | hi | median s | routes seen | failure reasons |", "|---|---|---|---|---|---|"]
    for tid in dict.fromkeys(r["task"] for r in rows):
        rs = [r for r in rows if r["task"] == tid]
        fails = sorted({f"{r['lang'][:2]}: {r['outcome']} / {r['why']}" for r in rs if not r["pass"]})
        md.append(f"| {tid} | {rate([r for r in rs if r['lang'] == 'telugu'])} | {rate([r for r in rs if r['lang'] == 'hindi'])} "
                  f"| {med(rs)} | {', '.join(sorted({str(r['route']) for r in rs}))} | {'<br>'.join(fails)} |")
    steps = [r for r in rows if r["jev_steps"] or r["groq_steps"]]
    if steps:
        js, gs = sum(r["jev_steps"] for r in steps), sum(r["groq_steps"] for r in steps)
        md += ["", f"Agent-loop runs: {len(steps)} · steps jev {js} / groq {gs} · mean steps per run {(js + gs) / len(steps):.1f} · "
               f"planner seconds per step {sum(r['planner_s'] for r in steps) / (js + gs):.2f} · "
               f"median planner s per run {statistics.median(r['planner_s'] for r in steps):.1f}"]
    (out / f"results_{tag}.md").write_text("\n".join(md) + "\n")
    print(f"overall {rate(rows)} -> eval/results_{tag}.md")


if __name__ == "__main__":
    main()
