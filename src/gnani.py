"""Gnani Prisma (STT) + Timbre (TTS) over plain requests. One lock = one active request."""
import hashlib, json, os, threading, time
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv(Path.home() / ".env")

ROOT = Path(__file__).resolve().parent.parent
STT_URL = "https://api.vachana.ai/stt/v3"
TTS_URL = "https://api.vachana.ai/api/v1/tts/inference"
_LOCK = threading.Lock()
_BACKOFF = (0.5, 1, 2)


class OutOfCredits(RuntimeError):
    pass


def _log(**kw):
    p = ROOT / "logs" / "gnani_usage.jsonl"
    p.parent.mkdir(exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps({"ts": round(time.time(), 2), **kw}) + "\n")


def _post(kind, url, **kw):
    """POST under the global lock; retry 429 with backoff; raise on 402/other errors."""
    key = os.environ.get("GNANI_API_KEY")
    if not key:
        raise RuntimeError("GNANI_API_KEY missing (put it in ~/.env)")
    with _LOCK:
        t0 = time.time()
        for wait in (*_BACKOFF, None):
            r = requests.post(url, headers={"X-API-Key-ID": key}, timeout=60, **kw)
            if r.status_code != 429 or wait is None:
                break
            time.sleep(wait)
        _log(kind=kind, ok=r.ok, status=r.status_code, cached=False,
             latency_s=round(time.time() - t0, 2))
        if r.status_code == 402:
            raise OutOfCredits("Gnani: insufficient credit (402)")
        if not r.ok:
            raise RuntimeError(f"Gnani {kind} {r.status_code}: {r.text[:300]}")
        return r


def keyterms():
    """Allowlist app names/aliases + test contacts. Latin-script only: Telugu-script keyterms pulled Hindi audio
    into Telugu script (Nov 6, measured)."""
    from .safety import load_allowlist
    allow = load_allowlist()
    return sorted({n for k, v in allow.items() for n in (k, *v.get("aliases", [])) if n.isascii()}
                  | {"YouTube", "Google Maps", "Test Amma", "Test Papa", "dialer", "phone", "call", "contacts", "settings", "chrome", "browser"})


def stt(wav_path, langs="te-IN,hi-IN,en-IN", fmt="codemix", keyterms=None):
    data = {"model": "prisma-v3.0", "language_code": langs, "format": fmt}
    if keyterms:
        data["keyterms"] = json.dumps(keyterms[:200], ensure_ascii=False)
    with open(wav_path, "rb") as f:
        r = _post("stt", STT_URL, data=data, files={"audio_file": f})
    return r.json()


def tts(text, lang, voice=None, speed=1.0, model="timbre-v3.0"):
    voice = voice or os.environ.get("TTS_VOICE", "Lakshmi")
    h = hashlib.sha256(f"{model}|{voice}|{lang}|{speed}|{text}".encode()).hexdigest()
    out = ROOT / "cache" / "tts" / f"{h}.wav"
    if out.exists():
        _log(kind="tts", ok=True, status=200, cached=True, chars=len(text))
        return out
    body = {"text": text, "voice": voice, "model": model, "language": lang, "speed": speed,
            "audio_config": {"sample_rate": 24000, "num_channels": 1, "sample_width": 2,
                             "encoding": "linear_pcm", "container": "wav"}}
    r = _post("tts", TTS_URL, json=body)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(r.content)
    return out


def usage_summary(path=ROOT / "logs" / "gnani_usage.jsonl"):
    """Per kind: billed calls, cache hits, errors, mean latency of billed calls."""
    out = {}
    for line in path.read_text().splitlines() if path.exists() else []:
        r = json.loads(line)
        s = out.setdefault(r["kind"], {"billed": 0, "cached": 0, "errors": 0, "lat": []})
        if r.get("cached"):
            s["cached"] += 1
            continue
        s["billed"] += 1
        s["errors"] += not r.get("ok")
        s["lat"].append(r.get("latency_s", 0))
    for s in out.values():
        lat = s.pop("lat")
        s["mean_latency_s"] = round(sum(lat) / len(lat), 2) if lat else None
    return out
