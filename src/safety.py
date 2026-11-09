"""Deterministic safety: deny/allow lists, private apps, forced-sensitive taps, yes/no + stop parsing, limits.
None of it trusts the LLM's own `sensitive` flag."""
import re
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
MAX_STEPS = 25  # hard limit
CHECKPOINTS = (15, 20)  # past these only if progress is real and Jev expects to finish soon
# USER RULE (Nov 6): never send a message or place a call, not even after a spoken "yes". The gate still asks (so the
# yes/no flow can be shown), but the commit tap is never made. Flip only when the user says so (WhatsApp later).
COMMIT_TAPS = False
MIN_ELEMENTS = 3  # fewer kept nodes after a settle = blank or FLAG_SECURE screen -> stop
_deny = yaml.safe_load((ROOT / "config/denylist.yaml").read_text())
_RX = re.compile(_deny["regex"], re.I)
_TEXT_RX = re.compile(_deny["text_regex"], re.I)
PRIVATE = set(_deny["private_packages"])
TEST_CONTACTS = tuple(_deny["test_contacts"])

# Tap labels that commit something. Matched on the element's text/desc, whatever the LLM said.
SENSITIVE_RX = re.compile(
    r"\b(send|call|dial|delete|remove|erase|pay|buy|purchase|order|confirm|submit|install|uninstall|reset|"
    r"factory|transfer|share|post|subscribe|accept|allow)\b"
    r"|పంపు|పంపించు|కాల్|తొలగించు|చెల్లించు|కొను|ధృవీకరించు"
    r"|भेज|कॉल|हटा|मिटा|भुगतान|खरीद|पुष्टि", re.I)

YES = {"yes", "yeah", "haan", "han", "haa", "ha", "ji", "avunu", "avnu", "aunu", "ounu",
       "అవును", "ఔను", "హా", "हाँ", "हां", "हा", "जी"}
NO = {"no", "nope", "nahi", "nahin", "na", "mat", "kadu", "vaddu", "ledu",
      "కాదు", "వద్దు", "లేదు", "नहीं", "नही", "ना", "मत"}
STOP = {"stop", "ruko", "ruk", "bas", "aapu", "apu", "appu", "aagu", "ఆపు", "ఆపండి", "ఆగు", "रुको", "रुकिए", "रुक", "बस"}
_SPLIT = re.compile(r"[\s.,!?;:'\"()।॥-]+")  # not \w: Python's \w drops Indic vowel signs (हाँ -> ह)


def words(text):
    return [w for w in _SPLIT.split((text or "").lower()) if w]


def is_yes(text):
    """Fails safe: yes only if a yes-word is present and no no/stop word. 'OK' deliberately not a yes."""
    w = set(words(text))
    return bool(w & YES) and not (w & (NO | STOP))


def is_stop(text):
    return bool(set(words(text)) & STOP)


# Keyterms per listening context, native script, few words. Measured Nov 6 on the user's 6 control clips (tuned on
# those same clips, n is tiny): codemix+3 langs heard అవును as 'Open now.', ఆపు as 'App.'; locked language fixed 5/6;
# ALL yes/no/stop words as keyterms made it worse (yes -> 'Appu no.', 'हाँ, रुक।').
GATE_KEYTERMS = {
    ("confirm", "te-IN"): ["అవును", "కాదు", "వద్దు"], ("confirm", "hi-IN"): ["हाँ", "नहीं"],
    ("stop", "te-IN"): ["ఆపు", "ఆపండి"], ("stop", "hi-IN"): ["रुको", "बस"],
}


def gate_stt(wav, lang, kind="confirm"):
    """STT for a short answer: lock to the task language + that context's answer words as keyterms."""
    from . import gnani
    code = {"te": "te-IN", "hi": "hi-IN", "hinglish": "hi-IN", "en": "en-IN"}.get(lang, "en-IN")
    return (gnani.stt(wav, langs=code, keyterms=GATE_KEYTERMS.get((kind, code))).get("transcript") or "").strip()


def load_allowlist():
    """-> {name: {pkg, aliases}}"""
    return yaml.safe_load((ROOT / "config/apps_allowlist.yaml").read_text())


_SHORTS = re.compile(r"\bshorts?\b|షార్ట్|शॉर्ट", re.I)


def shorts_blocked(label, goal):
    """User rule (Nov 6): never open YouTube Shorts unless the request asks for them."""
    return bool(_SHORTS.search(label or "")) and not _SHORTS.search(goal)


_PLAYBACK = re.compile(r"\b(play|watch|chalao|chala)\b|ప్లే|चला|प्ले", re.I)


def wants_playback(goal):
    return bool(_PLAYBACK.search(goal))


def making_progress(seen, n=5, min_new=3):
    """At least min_new of the last n screens are new to this run (scrolling counts; bouncing does not)."""
    return len(set(seen[-n:]) - set(seen[:-n])) >= min_new


def denied(pkg):
    return bool(pkg) and (pkg in _deny["packages"] or bool(_RX.search(pkg)))


# system surfaces the agent legitimately passes through (launcher, keyboard, permission dialogs)
SYSTEM_OK = {"com.android.launcher", "com.android.systemui", "com.google.android.inputmethod.latin",
             "com.google.android.permissioncontroller", "android"}


def outside_allowlist(pkg, allow):
    """Hard wall for the agent loop: any foreground app that is not allowlisted or a system surface."""
    return bool(pkg) and pkg not in SYSTEM_OK and pkg not in {v["pkg"] for v in allow.values()}


def denied_text(text):
    """Payment/banking request in the transcript itself -> block before any routing or LLM step."""
    return bool(_TEXT_RX.search(text or ""))


def forced_sensitive(label, pkg=None):
    # ponytail: Spotify result rows merge hidden button labels into one long label ("... Add to My Library ... remove"),
    # so a long Spotify label is a row, not a Remove button (Nov 9 false positive). Short labels still match.
    if pkg == "com.spotify.music" and len(label or "") > 60:
        return False
    return bool(SENSITIVE_RX.search(label or ""))
