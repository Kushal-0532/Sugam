import json
from pathlib import Path
import pytest
from src import safety
from src.agent import stuck

TRANSCRIPTS = Path(__file__).resolve().parent.parent / "eval" / "transcripts.json"


def test_denylist_packages_and_regex():
    for pkg in ("net.one97.paytm", "com.phonepe.app", "com.sbi.lotusintouch", "com.csam.icici.bank.imobile",
                "com.google.android.apps.walletnfcrel"):
        assert safety.denied(pkg), pkg
    for pkg in ("com.android.vending", "com.google.android.youtube", "com.oneplus.deskclock", "com.android.settings", "", None):
        assert not safety.denied(pkg), pkg  # Play Store: (?<!play)pay


def test_denied_text_in_three_scripts():
    for t in ("Paytm open చేసి money పంపించు.", "Paytm call कर, पैसे भेजो।", "PhonePe se 500 rupees bhejo",
              "పేటీఎం ఓపెన్ చెయ్యి", "बैंक का ऐप खोलो", "Google Pay kholo"):
        assert safety.denied_text(t), t
    for t in ("calculator open చేయి.", "Test Papa को message भेजा कि मैंने खाना खा लिया।", "YouTube లో devotional songs play చెయ్యి.",
              "कल सुबह सात बजे का alarm लगा दो।"):
        assert not safety.denied_text(t), t


def test_forced_sensitive_labels():
    for label in ("Send SMS", "Call", "Delete", "Pay now", "Confirm", "పంపు", "కాల్ చేయి", "भेजें", "कॉल करें", "हटाएं"):
        assert safety.forced_sensitive(label), label
    for label in ("Search", "Wi-Fi", "Display", "Calculator", "Alarm", "Add Alarm", "Callback settings", "", None):
        assert not safety.forced_sensitive(label), label


def test_yes_no_stop_parsing_three_scripts():
    for t in ("yes", "Haan.", "हाँ।", "हां", "అవును.", "avunu", "Ji haan"):
        assert safety.is_yes(t), t
    # fails safe: no, unclear, empty, OK, mixed yes+no, yes+stop -> not yes
    for t in ("no", "नहीं।", "కాదు.", "వద్దు", "OK", "okay", "", None, "Open now.", "అవన్నీ.", "haan nahi", "हाँ, रुक।"):
        assert not safety.is_yes(t), t
    for t in ("ruko", "रुको।", "ఆపు.", "stop!", "Appu.", "बस"):
        assert safety.is_stop(t), t
    for t in ("haan", "calculator open करो।", ""):
        assert not safety.is_stop(t), t


def test_real_clips_through_the_gate():
    """The user's recorded yes/no/stop clips, transcribed by eval/stt_eval.py with safety.gate_stt (real Prisma output,
    cached so this test costs 0 credits)."""
    if not TRANSCRIPTS.exists():
        pytest.skip("run eval/stt_eval.py first")
    t = json.loads(TRANSCRIPTS.read_text())
    for lang in ("telugu", "hindi"):
        assert safety.is_yes(t[f"confirm_yes_{lang}@gate"]["transcript"]), lang
        assert not safety.is_yes(t[f"confirm_no_{lang}@gate"]["transcript"]), lang
        assert safety.is_stop(t[f"stop_{lang}@gate"]["transcript"]), lang
        assert not safety.is_yes(t[f"stop_{lang}@gate"]["transcript"]), lang


def test_loop_detector_on_synthetic_hashes():
    assert stuck(["a", "b", "b", "b"]) and stuck(["x", "x", "x"])
    assert stuck(["a", "b", "a", "b"]) and stuck(["z", "a", "b", "a", "b"]) and not stuck(["a", "b", "c", "b"])
    assert not stuck(["a", "b", "b"]) and not stuck(["b", "b"]) and not stuck([])


def test_commit_taps_disabled_user_rule():
    """User rule Nov 6: never send or call, even after yes. Handlers and agent loop check this switch."""
    assert safety.COMMIT_TAPS is False
    from src import handlers
    assert handlers.COMMIT_TAPS is False


def test_checkpoint_progress_signal():
    from src.safety import making_progress
    assert making_progress(list("abcdefgh"))  # all new
    assert not making_progress(list("abababab"))  # bouncing
    assert not making_progress(list("abcdeeeee"))  # stuck on one screen
    assert not making_progress(list("abcdeabcab"))  # revisiting old screens


def test_wants_playback():
    from src.safety import wants_playback
    for g in ("search for 8bitryan and play his latest video", "watch the first video", "YouTube లో songs play చెయ్యి", "गाने चलाओ"):
        assert wants_playback(g), g
    for g in ("open the videos tab", "search for playstation games", "display the results"):
        assert not wants_playback(g), g


def test_outside_allowlist():
    allow = {"yt": {"pkg": "com.google.android.youtube"}}
    assert not safety.outside_allowlist("com.google.android.youtube", allow)
    assert not safety.outside_allowlist("com.android.launcher", allow)
    assert safety.outside_allowlist("com.android.vending", allow)
