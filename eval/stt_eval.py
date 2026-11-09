"""Transcribe every clip in audio/ ONCE (Prisma, codemix, same keyterms as --voice) -> eval/transcripts.json,
then score keyword groups from tasks.yaml -> eval/stt_results.md. Re-runs reuse transcripts.json (0 credits);
--force re-transcribes."""
import json, sys, time
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import gnani, safety  # noqa: E402

OUT = ROOT / "eval" / "transcripts.json"


def hit(text, groups):
    t = text.lower()
    return [any(k.lower() in t for k in map(str, g)) for g in groups]


def main(force=False):
    tasks = yaml.safe_load((ROOT / "eval" / "tasks.yaml").read_text())
    done = json.loads(OUT.read_text()) if OUT.exists() and not force else {}
    kt = gnani.keyterms()
    for tid in tasks:
        for lang in ("telugu", "hindi"):
            clip = f"{tid}_{lang}"
            if clip in done:
                continue
            t = time.time()
            r = gnani.stt(ROOT / "audio" / f"{clip}.flac", keyterms=kt)
            done[clip] = {"transcript": (r.get("transcript") or "").strip(),
                          "detected": r.get("detected_language_code"), "stt_s": round(time.time() - t, 2)}
            OUT.write_text(json.dumps(done, ensure_ascii=False, indent=1))  # save as we go: a crash keeps paid calls
            print(clip, done[clip])
    for tid in (t for t, v in tasks.items() if v["kind"] == "task"):  # "after" config: user's language set once (+ en for code-mix)
        for lang, codes in (("telugu", "te-IN,en-IN"), ("hindi", "hi-IN,en-IN")):
            clip = f"{tid}_{lang}@lang"
            if clip not in done:
                t = time.time()
                r = gnani.stt(ROOT / "audio" / f"{tid}_{lang}.flac", langs=codes, keyterms=kt)
                done[clip] = {"transcript": (r.get("transcript") or "").strip(),
                              "detected": r.get("detected_language_code"), "stt_s": round(time.time() - t, 2)}
                OUT.write_text(json.dumps(done, ensure_ascii=False, indent=1))
                print(clip, done[clip])
    for tid in (t for t, v in tasks.items() if v["kind"] == "control"):  # yes/no/stop through the real gate config
        for lang, code in (("telugu", "te"), ("hindi", "hi")):
            clip = f"{tid}_{lang}@gate"
            if clip not in done:
                t = time.time()
                done[clip] = {"transcript": safety.gate_stt(ROOT / "audio" / f"{tid}_{lang}.flac", code,
                                                              "stop" if tid == "stop" else "confirm"),
                              "detected": code, "stt_s": round(time.time() - t, 2)}
                OUT.write_text(json.dumps(done, ensure_ascii=False, indent=1))
                print(clip, done[clip])
    rows, ok, ok2 = [], 0, 0
    scored = [(tid, lang) for tid, v in tasks.items() if v["stt"] for lang in ("telugu", "hindi")]
    for tid, lang in scored:
        d, d2 = done[f"{tid}_{lang}"], done[f"{tid}_{lang}@lang"]
        h, h2 = hit(d["transcript"], tasks[tid]["stt"]), hit(d2["transcript"], tasks[tid]["stt"])
        ok += all(h)
        ok2 += all(h2)
        rows.append(f"| {tid}_{lang} | {d['detected']} | {sum(h)}/{len(h)} | {d['transcript']} | {sum(h2)}/{len(h2)} | {d2['transcript']} |")
    lat = sorted(d["stt_s"] for d in done.values())
    md = [f"# STT eval (Gnani Prisma v3.0, codemix) — {time.strftime('%Y-%m-%d %H:%M')}", "",
          f"Clips: 30 recorded by the user (te + hi). Keyword pass (all groups hit): default config (te,hi,en auto-detect) "
          f"**{ok}/{len(scored)}**; language set per user (te-IN,en-IN or hi-IN,en-IN) **{ok2}/{len(scored)}**. "
          f"STT latency p50 {lat[len(lat) // 2]} s, max {lat[-1]} s (all calls).", "",
          "| clip | detected (default) | hit | transcript (default) | hit (lang set) | transcript (lang set) |",
          "|---|---|---|---|---|---|", *rows, "",
          "Control clips (scored by tests/test_safety.py, not here). Plain = codemix + 3 langs + app keyterms "
          "(the command config); `@gate` = safety.gate_stt (task language locked + answer-word keyterms):", "",
          *(f"- {c}: `{d['transcript']}` [{d['detected']}]" for c, d in done.items()
            if tasks[c.split("@")[0].rsplit('_', 1)[0]]["kind"] == "control")]
    (ROOT / "eval" / "stt_results.md").write_text("\n".join(md) + "\n")
    print(f"keyword pass {ok}/{len(scored)} -> eval/stt_results.md")


if __name__ == "__main__":
    main("--force" in sys.argv)
