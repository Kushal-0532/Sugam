import argparse, json, time
from pathlib import Path
from . import agent, audio_io, glow, gnani, safety

ROOT = Path(__file__).resolve().parent.parent
TTS_LANG = {"te": "te-IN", "hi": "hi-IN", "hinglish": "auto", "en": "en-IN"}


def make_speak(narrate, stats):
    def speak(text, lang, step=False):
        if step and not narrate:
            return
        print(f"🔊 {text}")
        t = time.time()
        try:
            wav = gnani.tts(text, TTS_LANG.get(lang, "en-IN"))
        except gnani.OutOfCredits:
            raise
        except Exception as e:  # narration failing must not kill the task
            print(f"tts failed: {e}")
            return
        stats["tts_s"] = round(stats.get("tts_s", 0) + time.time() - t, 2)
        audio_io.play(wav)
    return speak


def make_ask(a, speak=None):
    """Confirmation gate for live sensitive taps. Answer source: --confirm-wav (STT), else mic (--voice), else typed.
    Only a parsed yes passes (safety.is_yes); empty / unclear / STT error = no. ask.reply(prompt, lang) is the
    free-form version (spotify_play): speaks a dynamic prompt, returns what the user said ('' on error)."""
    def listen(lang, prompt):
        try:
            if a.confirm_wav or a.voice:
                wav = a.confirm_wav or ROOT / "logs" / f"confirm_{int(time.time())}.wav"
                if not a.confirm_wav:
                    audio_io.record(wav)  # ponytail: live mic path not yet verified end to end (deferred by user)
                return safety.gate_stt(wav, lang)
            return input(prompt)
        except gnani.OutOfCredits:
            raise
        except Exception as e:
            print(f"answer failed ({e})")
            return ""

    def ask(label, lang):
        print(f"❓ confirm: {label}")
        if speak:
            speak(agent.phrase("confirm", lang), lang)
            audio_io.wait()  # the question finishes before we listen
        ans = listen(lang, "answer (yes/haan/avunu = yes, anything else = no): ")
        ok = safety.is_yes(ans)
        print(f"heard answer: {ans!r} -> {'YES' if ok else 'NO'}")
        return ok

    def reply(prompt, lang):
        print(f"❓ {prompt}")
        if speak:
            speak(prompt, lang)
            audio_io.wait()
        ans = listen(lang, "answer (yes / another song / no): ")
        print(f"heard answer: {ans!r}")
        return ans
    ask.reply = reply
    return ask


def voice(a):
    keyterms = gnani.keyterms()
    stats = {}
    speak = make_speak(a.narrate, stats)
    for attempt in (0, 1):  # empty transcript -> say so and re-prompt once
        wav = a.wav or ROOT / "logs" / f"mic_{int(time.time())}.wav"
        if not a.wav:
            glow.state("listening")
            stats["record_s"] = audio_io.record(wav)
        glow.state("thinking")
        t = time.time()
        res = gnani.stt(wav, keyterms=keyterms)
        stats["stt_s"] = round(time.time() - t, 2)
        text = (res.get("transcript") or "").strip()
        if text or a.wav:
            break
        speak(agent.phrase("didnt_hear", "en"), "en")
    print(f"heard [{res.get('detected_language_code')}]: {text!r}")
    if not text:
        glow.state("off")
        audio_io.wait()
        return
    t, tts0 = time.time(), stats.get("tts_s", 0)
    out = agent.run_routed(text, a.dry_run, a.device, force_agent=a.agent, speak=speak, stats=stats,
                           ask=make_ask(a, speak))
    stats["task_s"] = round(time.time() - t - stats.get("route_s", 0) - (stats.get("tts_s", 0) - tts0), 2)
    audio_io.wait()
    rec = {"ts": int(time.time()), "input": str(a.wav or "mic"), "transcript": text,
           "detected": res.get("detected_language_code"), "outcome": out, **stats}
    (ROOT / "logs").mkdir(exist_ok=True)
    with (ROOT / "logs" / "voice_runs.jsonl").open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("timings:", {k: v for k, v in stats.items() if k.endswith("_s")})


def warm():
    """Generate every fixed phrase once (cached after), plus Hinglish `auto` copies to compare with `hi-en`."""
    import yaml
    p = yaml.safe_load((ROOT / "config" / "phrases.yaml").read_text())
    for key, by_lang in p.items():
        for lang, text in by_lang.items():
            print(f"{key:11} {lang:9} {gnani.tts(text, TTS_LANG[lang])}")
    for key in ("working", "done", "failed"):
        print(f"{key:11} auto      {gnani.tts(p[key]['hinglish'], 'auto')}")


p = argparse.ArgumentParser()
g = p.add_mutually_exclusive_group(required=True)
g.add_argument("--text")
g.add_argument("--voice", action="store_true", help="push-to-talk mic -> Prisma STT -> agent -> Timbre TTS")
g.add_argument("--wav", type=Path, help="like --voice, but transcribe this WAV instead of the mic")
g.add_argument("--warm", action="store_true", help="pre-generate phrases.yaml audio")
g.add_argument("--usage", action="store_true", help="summarise logs/gnani_usage.jsonl")
p.add_argument("--dry-run", action="store_true")
p.add_argument("--agent", action="store_true", help="skip the router, force the LLM agent loop")
p.add_argument("--narrate", action="store_true", help="voice mode: speak every agent step, not just start/result")
p.add_argument("--device")
p.add_argument("--confirm-wav", type=Path, help="answer clip for the yes/no gate (live sensitive taps)")
a = p.parse_args()
if a.text:
    agent.run_routed(a.text, a.dry_run, a.device, force_agent=a.agent, ask=make_ask(a))
elif a.voice or a.wav:
    voice(a)
elif a.warm:
    warm()
else:
    print(json.dumps(gnani.usage_summary(), indent=1))
