"""Read the glow colour on the left edge of each take (10 fps) -> state runs. No numpy: ffmpeg scales the edge strip to 1 pixel."""
import colorsys, subprocess, sys, json
def states(path, fps=10):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"crop=24:1500:0:600,fps={fps},scale=1:1:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    out = []
    for i in range(0, len(raw) - 2, 3):
        r, g, b = raw[i] / 255, raw[i + 1] / 255, raw[i + 2] / 255
        h, s, v = colorsys.rgb_to_hsv(r, g, b); h *= 360
        out.append((h, s, v))
    return out
def label(h, s, v):
    if s < .28 or v < .12: return "none"
    if h < 40 or h > 340: return "red"
    if 80 <= h < 160: return "green"
    if 160 <= h < 200: return "cyan"
    if 200 <= h < 255: return "blue"
    if 255 <= h <= 340: return "purple"
    return "none"
if __name__ == "__main__":
    res = {}
    for n in sys.argv[1:]:
        st = [label(*x) for x in states(f"demo/{n}.mp4")]
        runs, i = [], 0
        while i < len(st):
            j = i
            while j < len(st) and st[j] == st[i]: j += 1
            runs.append((round(i / 10, 1), round(j / 10, 1), st[i])); i = j
        res[n] = runs
        print(n, " ".join(f"{a}-{b}:{s}" for a, b, s in runs if b - a >= .3))
    json.dump(res, open("video/work/glow_runs.json", "w"))
