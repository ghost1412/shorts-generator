"""Which framing suits a game video: the whole picture over a blurred copy ("fit") or a full-screen portrait crop ("crop").

A centre crop of a 16:9 picture keeps only about a third of its width. It loses things that sit at the sides: the minimap,
health bars and other HUD parts (they stay put while the scene moves), and the game's own subtitles when they are wider than
the crop. So a picture with such side detail is framed "fit", and a clean picture (a cutscene close-up, a menu-free view)
"crop". The measurements are on small grey frames inside the chosen moments; every moment votes."""
import subprocess

THUMB_W = 320
HUD_SHARE = 0.012          # share of the side strips that is sharp AND unchanging over a few seconds (HUD)
SUBTITLE_SHARE = 0.004     # share of the subtitle band outside the crop that is near-white (text)
GRAD_MIN = 14.0
STILL_MAX = 5.0
MOTION_MIN = 3.0           # mean change of the centre over the shots below which the picture counts as held


def _dims(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", video],
                       capture_output=True, text=True)
    w, h = r.stdout.strip().split(",")[:2]
    return int(w), int(h)


def _frame(video, t, w, h):
    import numpy as np
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{max(0.0, t):.2f}", "-i", video, "-frames:v", "1",
                        "-vf", f"scale={w}:{h},format=gray", "-f", "rawvideo", "-"], capture_output=True)
    if len(r.stdout) < w * h:
        return None
    return np.frombuffer(r.stdout[:w * h], dtype=np.uint8).reshape(h, w).astype(np.float32)


def measure(video, start, end, size=None, shots=4, gap=1.5):
    """{"hud": share, "subtitle": share} for the window start-end (seconds), or None when frames cannot be read."""
    import numpy as np
    width, height = size or _dims(video)
    h = max(40, int(round(THUMB_W * height / width)))
    t0 = start + max(0.0, (end - start - gap * (shots - 1)) / 2)
    frames = [f for f in (_frame(video, t0 + i * gap, THUMB_W, h) for i in range(shots)) if f is not None]
    if len(frames) < 3:
        return None
    crop_w = min(THUMB_W, h * 9 / 16)
    left, right = int((THUMB_W - crop_w) / 2), int((THUMB_W + crop_w) / 2)
    outside = np.ones((h, THUMB_W), dtype=bool)
    outside[:, left:right] = False
    stack = np.stack(frames)
    still = stack.std(axis=0) < STILL_MAX
    gy, gx = np.gradient(frames[len(frames) // 2])
    sharp = np.hypot(gx, gy) > GRAD_MIN
    hud = float((still & sharp)[outside].mean()) if outside.any() else 0.0
    if float(stack.std(axis=0)[:, left:right].mean()) < MOTION_MIN:
        hud = 0.0                              # nothing moves: a held shot, so "unchanging" says nothing about a HUD
    band = np.zeros((h, THUMB_W), dtype=bool)
    band[int(h * 0.76):int(h * 0.96), int(THUMB_W * 0.08):int(THUMB_W * 0.92)] = True
    band &= outside
    white = np.mean([(f >= 235)[band].mean() for f in frames]) if band.any() else 0.0
    return {"hud": hud, "subtitle": float(white)}


def decide(scores):
    """("fit" | "crop", reason) from the per-moment measurements (None entries are ignored)."""
    got = [s for s in scores if s]
    if not got:
        return "fit", "no frames could be measured"
    votes = [(s["hud"] >= HUD_SHARE) or (s["subtitle"] >= SUBTITLE_SHARE) for s in got]
    fit_n = sum(votes)
    hud = max(s["hud"] for s in got)
    sub = max(s["subtitle"] for s in got)
    if fit_n * 3 >= len(got):                  # crop only when clearly most moments are clean: fit is the safe choice
        what = "a HUD or subtitles at the sides" if (hud >= HUD_SHARE or sub >= SUBTITLE_SHARE) else "side detail"
        return "fit", f"{fit_n} of {len(got)} moments have {what}"
    return "crop", f"only {fit_n} of {len(got)} moments have side detail (HUD {hud:.3f}, subtitles {sub:.4f})"


def choose(video, highlights, size=None, max_moments=6):
    """("fit" | "crop", reason) for a video and the moments picked from it."""
    wins = [(float(h["start"]), float(h["end"])) for h in highlights][:max_moments]
    try:
        scores = [measure(video, s, e, size=size) for s, e in wins]
    except Exception as e:
        return "fit", f"could not measure ({e})"
    return decide(scores)
