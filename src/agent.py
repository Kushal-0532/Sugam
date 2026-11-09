"""Agent loop: snapshot -> planner -> safety -> execute -> settle. Writes a jsonl run log."""
import functools, json, os, time
from pathlib import Path
import yaml
from . import glow, handlers, jev, phone, planner, safety

ROOT = Path(__file__).resolve().parent.parent


@functools.cache
def _phrases():
    return yaml.safe_load((ROOT / "config" / "phrases.yaml").read_text())


def phrase(key, lang):
    return _phrases()[key].get(lang) or _phrases()[key]["en"]


def outcome_phrase(out):
    return {"done": "done", "dry_run_ok": "dry_run", "denied_app": "blocked", "private_app": "blocked",
            "blocked_contact": "blocked_contact", "cancelled_by_user": "cancelled",
            "confirmed_not_committed": "dry_run"}.get(out, "failed")


def use_jev():
    return os.environ.get("PLANNER", "groq") == "jev"


script_lang = planner.script_lang


def jev_decide(text, stats):
    """Jev makes the task decision. -> (route, pin): route = no details needed, skip Groq; pin = Groq only fills in the
    details of this task; (None, None) = Jev unsure or down, Groq decides everything (fixed Qwen sending a clear Chrome
    search to the agent loop, Nov 6: Jev said chrome_search 0.99)."""
    try:
        allow = safety.load_allowlist()
        j, s = jev.route(text, allow)
    except Exception as e:
        print(f"jev route failed ({e}); using groq")
        return None, None
    if stats is not None:
        stats.update(jev_task=j["task"], jev_conf=j["conf"], jev_route_s=s)
    if j["conf"] < jev.ROUTE_MIN:
        return None, None
    base = {"lang": script_lang(text), "goal": text}
    if j["task"] in ("wifi_settings", "agent"):
        return {"task": j["task"], **base}, None
    if j["task"] == "open_app":
        return ({"task": "open_app", "pkg": allow[j["app"]]["pkg"], **base}, None) if j["app_conf"] >= jev.ROUTE_MIN else (None, None)
    return None, j["task"]


def run_routed(text, dry_run=True, serial=None, say=print, force_agent=False, speak=None, stats=None, ask=None):
    """run_routed, but an exhausted LLM quota is its own outcome: never reported as an agent failure."""
    try:
        out = _run_routed(text, dry_run, serial, say, force_agent, speak, stats, ask)
    except planner.RateLimited as e:
        say(f"outcome: llm_rate_limited ({e})")
        if speak:
            speak(phrase("failed", script_lang(text)), script_lang(text))
        out = "llm_rate_limited"
    glow.outcome(out)
    return out


def _run_routed(text, dry_run=True, serial=None, say=print, force_agent=False, speak=None, stats=None, ask=None):
    """Router entry: known tasks -> deterministic handler (no LLM steps); everything else -> agent loop.
    speak(text, lang, step=False) is the voice hook (None = silent); stats gets route_s/task/lang.
    ask(label, lang) -> bool is the confirmation gate for live sensitive taps (None = always no)."""
    if safety.denied_text(text):  # payment/banking request: blocked before any LLM sees it
        lang = "te" if any("ఀ" <= c <= "౿" for c in text) else "hi" if any("ऀ" <= c <= "ॿ" for c in text) else "en"
        say("outcome: denied_app (payment/banking/blocked-app request in transcript)")
        if stats is not None:
            stats.update(route_s=0, task="denied", lang=lang)
        if speak:
            speak(phrase("blocked", lang), lang)
        return "denied_app"
    t = time.time()
    r = {"task": "agent", "lang": script_lang(text), "goal": text} if force_agent else None
    pin = None
    if not r and use_jev():
        r, pin = jev_decide(text, stats)
    r = r or planner.understand(text, pin)
    if stats is not None:
        stats.update(route_s=round(time.time() - t, 2), task=r["task"], lang=r["lang"])
    say(f"route: {r['task']} [{r['lang']}] {({k: v for k, v in r.items() if k in ('hour', 'minute', 'minutes', 'query', 'contact', 'text')})}")
    if r["task"] == "blocked_contact":
        say(f"outcome: blocked_contact ({r.get('contact')!r} is not a test contact)")
        if speak:
            speak(phrase("blocked_contact", r["lang"]), r["lang"])
        return "blocked_contact"
    glow.state("acting")
    if speak:
        speak(phrase("working", r["lang"]), r["lang"])
    if r["task"] in handlers.HANDLERS:
        d = phone.connect(serial)
        t_h = time.time()
        confirm = lambda label: bool(ask) and ask(label, r["lang"])
        if getattr(ask, "reply", None):  # free-form answer hook (spotify_play), same language as the run
            confirm.reply = lambda prompt: ask.reply(prompt, r["lang"])
        out = handlers.HANDLERS[r["task"]](d, r, dry_run, confirm)
        hlog = ROOT / "logs" / f"run_{int(t_h)}.jsonl"
        hlog.parent.mkdir(exist_ok=True)
        hlog.write_text(json.dumps({"handler": r["task"], "outcome": out, "dry_run": dry_run, "route_s": (stats or {}).get("route_s"),
                                    "handler_s": round(time.time() - t_h, 2)}, ensure_ascii=False) + "\n")
        say(f"outcome: {out} (handler: {r['task']})")
        if speak:
            speak(phrase(outcome_phrase(out), r["lang"]), r["lang"])
        return out
    # the router's gloss can drop details ("perform multiplication" lost "12 times 8"): the user's words stay the goal
    goal = text if r["goal"] == text else f"{text}  (English gloss, may be lossy: {r['goal']})"
    return run(goal, r["lang"], dry_run, serial, say, speak, ask, stats)


def stuck(hashes, n=3):
    """Loop detector: the last n post-action screens are identical, or the last 4 flip A/B/A/B."""
    if len(hashes) >= 4 and hashes[-1] == hashes[-3] and hashes[-2] == hashes[-4]:
        return True
    return len(hashes) >= n and len(set(hashes[-n:])) == 1


def keep_going(goal, els, history, seen):
    """Step checkpoint: both real progress and Jev's yes are needed. -> (bool, why). Jev down or off = stop."""
    if not safety.making_progress(seen):
        return False, "no progress in the last 5 screens"
    if not use_jev():
        return False, "no confidence source (PLANNER is not jev)"
    try:
        p, s = jev.reachable(goal, els, history)
    except Exception as e:
        return False, f"jev error: {e}"[:120]
    return p >= jev.REACH_MIN, f"jev reachable {p} ({s} s)"


def run(goal, lang="en", dry_run=True, serial=None, say=print, speak=None, ask=None, stats=None):
    d = phone.connect(serial)
    allow = safety.load_allowlist()
    log = ROOT / "logs" / f"run_{int(time.time())}.jsonl"
    log.parent.mkdir(exist_ok=True)
    history, seen, outcome, private, done_rejected = [], [], "step_limit", False, False
    back_tried = False
    jev_same, counts = 0, {"jev_steps": 0, "groq_steps": 0, "planner_s": 0.0}  # jev_same: Jev steps with no screen change
    for step in range(safety.MAX_STEPS):
        t0 = time.time()
        els, h, pkg = phone.snapshot(d)
        if safety.denied(pkg):
            d.press("home"); outcome = "denied_app"; say(f"stopped: denylisted app {pkg}"); break
        if pkg in safety.PRIVATE:  # real contacts on screen: never sent to the LLM, never screenshotted
            d.press("home"); outcome, private = "private_app", True; say(f"stopped: private app {pkg}"); break
        if safety.outside_allowlist(pkg, allow):  # a tap led into an app we never allowed: nothing reaches the LLMs
            time.sleep(1.5)  # system popups (e.g. com.oplus.battery "fully charged", seen live Nov 8) vanish; a real app stays
            els, h, pkg = phone.snapshot(d)
        if safety.outside_allowlist(pkg, allow):
            d.press("home"); outcome = "denied_app"; say(f"stopped: app not in allowlist {pkg}"); break
        if len(els) < safety.MIN_ELEMENTS:
            time.sleep(1)
            els, h, pkg = phone.snapshot(d)
            if len(els) < safety.MIN_ELEMENTS:
                outcome = "blank_or_secure"; say("stopped: blank or secure screen"); break
        if step in safety.CHECKPOINTS:
            go, why = keep_going(goal, els, history, seen)
            say(f"checkpoint at step {step}: {'continue' if go else 'stop'} ({why})")
            log.open("a").write(json.dumps({"step": step, "checkpoint": go, "why": why}, ensure_ascii=False) + "\n")
            if not go:
                outcome = "checkpoint_stop"; break
        a, info, err = None, {}, None
        if use_jev():
            if jev_same >= 2:  # Jev isn't moving the screen: let Groq take this step
                info, jev_same = {"why": "screen unchanged after 2 jev steps"}, 0
            else:
                a, info = jev.step(goal, els, history, allow, lambda k: phrase(k, lang))
        src = "jev" if a else "groq"
        if not a:
            a, err = planner.next_action(goal, lang, els, history, allow)
            if not a and use_jev():  # Groq failed twice: take Jev's best guess instead of ending the run
                a, info = jev.step(goal, els, history, allow, lambda k: phrase(k, lang), force=True)
                if a:
                    src, info = "jev", {**info, "fallback": err}
        t_llm = time.time() - t0
        counts[f"{src}_steps"] += 1
        counts["planner_s"] = round(counts["planner_s"] + t_llm, 2)
        if stats is not None:
            stats.update(counts)
        if not a:
            outcome = f"planner_error: {err}"; break
        if a["action"] == "open_app" and safety.denied(a["app"]):
            outcome = "denied_app"; break
        rec = {"step": step, "pkg": pkg, "hash": h, "action": a, "llm_s": round(t_llm, 2), "src": src, "jev": info}
        if "element_id" in a:  # what the id meant on this screen (allowlisted apps only; logs/ is gitignored)
            e = els[a["element_id"]]
            rec["on"] = (e["text"] or e["desc"] or e["rid"])[:60]
        # the model can say "playing" on a list screen (Nov 6): on YouTube a play request needs a real player on screen
        # ponytail: YouTube only; add other apps' player ids when the agent plays media there
        if a["action"] == "done" and pkg == handlers.YT and safety.wants_playback(goal) and not d(resourceId=handlers.YT + ":id/watch_player").exists:
            rec["rejected"] = "done without a video player"
            log.open("a").write(json.dumps(rec, ensure_ascii=False) + "\n")
            if done_rejected:
                outcome = "unverified_done"; say("stopped: said done twice with no video player on screen"); break
            done_rejected = True
            say("skipped: done, but no video player is on screen")
            history.append({"action": "done", "screen_changed": False, "rejected": "no video player on screen: the video is not playing yet"})
            continue
        say(f"[{step}] {a['action']} {a.get('element_id', a.get('app', ''))} — {a['say']}")
        final = a["action"] in ("done", "fail", "ask_user")
        if speak:  # the LLM's own `say` is the final answer; per-step says only with --narrate
            speak(a["say"], lang, step=not final)
        if final:
            outcome = {"done": "done", "fail": "failed", "ask_user": "asked_user"}[a["action"]]
            log.open("a").write(json.dumps(rec, ensure_ascii=False) + "\n"); break
        if a["action"] == "tap":
            e = els[a["element_id"]]
            label = e["text"] or e["desc"]
            if safety.shorts_blocked(label, goal):  # not tapped: the model is told and picks something else
                say(f"skipped: Shorts not requested ({label[:40]!r})")
                history.append({"action": "tap", "on": label[:40], "screen_changed": False, "rejected": "Shorts not requested: pick a regular video"})
                rec["rejected"] = "shorts"
                log.open("a").write(json.dumps(rec, ensure_ascii=False) + "\n")
                continue
            forced = safety.forced_sensitive(label, pkg)
            outward = info.get("outward", 0) > 0.5  # Jev's yes/no: can only add caution, never removes it
            if a.get("sensitive") or forced or outward:
                rec.update(would_tap=label, forced_sensitive=forced, jev_outward=info.get("outward"))
                if dry_run:
                    outcome = "dry_run_ok"; say(f"dry-run: would have tapped '{label}'")
                    log.open("a").write(json.dumps(rec, ensure_ascii=False) + "\n"); break
                if not (ask and ask(label, lang)):
                    outcome = "cancelled_by_user"; say(f"cancelled: '{label}' not confirmed")
                    log.open("a").write(json.dumps(rec, ensure_ascii=False) + "\n"); break
                rec["confirmed"] = True
                if not safety.COMMIT_TAPS:  # user rule: never send/call/pay, even after yes
                    outcome = "confirmed_not_committed"; say(f"confirmed, but commit taps are disabled: '{label}' not tapped")
                    log.open("a").write(json.dumps(rec, ensure_ascii=False) + "\n"); break
        phone.execute(d, a, els)
        h2 = phone.settle(d)
        # Spotify shows a full-screen promo (Premium Rewards, Nov 9) right after launch that is NOT in the accessibility
        # tree, so a tap on the home screen underneath changes nothing. Back closes it. Once per run.
        # ponytail: Spotify only; a screenshot check would generalise it, but Spotify is not private-read anymore, not vision-read
        if a["action"] == "tap" and h2 == h and pkg == "com.spotify.music" and not back_tried:
            back_tried = True
            d.press("back")
            h2 = phone.settle(d)
            rec["back_pressed"] = "tap changed nothing on Spotify: pressed back once (hidden promo overlay)"
        seen.append(h2)
        jev_same = jev_same + 1 if src == "jev" and h2 == h else 0
        rec["exec_s"] = round(time.time() - t0 - t_llm, 2)
        hist = {k: a[k] for k in ("action", "text", "app", "direction", "repeat") if k in a}
        if "element_id" in a:  # label, not just the id: ids shift between screens and mean nothing to the model later
            e = els[a["element_id"]]
            hist["on"] = (e["text"] or e["desc"] or e["rid"])[:40]
        history.append({**hist, "screen_changed": h2 != h})
        log.open("a").write(json.dumps(rec, ensure_ascii=False) + "\n")
        if (phone.current(d)["package"] == handlers.YT and safety.wants_playback(goal)
                and d(resourceId=handlers.YT + ":id/watch_player").exists):  # video is playing: no stray extra tap
            outcome = "done"; say("done: video player is on screen")
            if speak:
                speak(phrase("done", lang), lang)
            break
        if stuck(seen):
            outcome = "stuck_loop"; break
    if not private:
        shot = ROOT / "logs" / f"{log.stem}.png"
        d.screenshot(str(shot))
        say(f"outcome: {outcome} | log: {log} | screenshot: {shot}")
    else:
        say(f"outcome: {outcome} | log: {log} | no screenshot (private app)")
    if speak and outcome not in ("done", "failed", "asked_user"):  # loop ended without an LLM final say
        speak(phrase(outcome_phrase(outcome), lang), lang)
    return outcome
