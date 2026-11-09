"""Screen-edge glow on the phone (android/glow app). Fire-and-forget: silent no-op if the app/phone is absent."""
import os
import subprocess

_CMD = "adb shell am broadcast -a com.gnani.glow.STATE --es s {}"


def state(s, off_after=None):
    if os.environ.get("GLOW", "1") == "0":
        return
    cmd = _CMD.format(s) + (f"; sleep {off_after}; " + _CMD.format("off") if off_after else "")
    subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def outcome(out):
    """done/dry-run -> green, everything else -> red; then fades off."""
    state("done" if out in ("done", "dry_run_ok", "confirmed_not_committed") else "blocked", off_after=3)
