"""Mic + speaker through arecord/aplay. Push-to-talk: Enter starts, Enter stops, 30 s cap."""
import select, signal, subprocess, sys, time

CAP_S = 30
_playing = None


def record(path, cap=CAP_S):
    """Record 16 kHz mono S16 WAV to `path`. Returns seconds recorded."""
    input("🎙  Press Enter, speak, then press Enter again (max 30 s)... ")
    p = subprocess.Popen(["arecord", "-q", "-f", "S16_LE", "-r", "16000", "-c", "1", "-d", str(cap), str(path)])
    t0 = time.time()
    if select.select([sys.stdin], [], [], cap)[0]:
        sys.stdin.readline()
    else:
        print(f"(stopped at the {cap} s cap)")
    p.send_signal(signal.SIGINT)  # arecord finalises the WAV header on SIGINT; no-op if it already exited at -d
    p.wait()
    return round(time.time() - t0, 2)


def play(path):
    """Play in the background. A new clip waits for the previous one, so narration never overlaps."""
    global _playing
    wait()
    _playing = subprocess.Popen(["aplay", "-q", str(path)])


def wait():
    if _playing:
        _playing.wait()
