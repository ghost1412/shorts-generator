"""Auto enhance: fix each clip the way an editor does before styling it.

A few frames of a clip are measured (how bright, how much contrast, any colour cast, how colourful, how noisy) and an FFmpeg filter
chain is built that corrects only what is off, within safe limits:

* brightness: an underexposed clip is lifted (gamma), a washed-out or flat one gets its black and white points stretched;
* colour cast: a clear tint is pulled back part of the way (a warm sunset or a blue lake is left alone: those casts are the look);
* colour: a dull clip gets a little saturation;
* sharpness: a light unsharp mask; noise: light denoising, only on dark noisy clips.

`--enhance_strength subtle|medium` scales every correction. It cannot add detail that is not in the footage: it improves what is there.
Nothing is sent anywhere; everything is measured and rendered locally with FFmpeg.
"""
import math
import os
import re
import subprocess

import numpy as np

STRENGTHS = {"subtle": 0.5, "medium": 1.0}
TARGET_MEDIAN = 0.42          # the middle grey of a well exposed clip (0..1)


def sample_frames(video, ffmpeg=None, n=5, width=160, duration=None, run=subprocess.run):
    """[float RGB arrays (h, w, 3) in 0..1] of n frames spread over the clip (first and last 10% skipped); [] on failure."""
    if ffmpeg is None:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    if duration is None:
        r = run([ffmpeg, "-hide_banner", "-i", video], capture_output=True, text=True)
        m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr or "")
        duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 10.0
    frames = []
    for k in range(n):
        t = max(0.0, duration * (0.1 + 0.8 * (k + 0.5) / n))
        r = run([ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1",
                 "-vf", f"scale={width}:-2:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
        if r.returncode != 0 or not r.stdout:
            continue
        # the height is whatever the scaler produced: 3 bytes per pixel, width known
        px = len(r.stdout) // 3
        if px % width:
            continue
        frames.append(np.frombuffer(r.stdout, np.uint8).reshape(px // width, width, 3).astype(np.float32) / 255.0)
    return frames


def measure(frames):
    """Statistics of the frames: luma percentiles p1/p50/p99, channel means, mean saturation, noise (0..1), or None without frames."""
    if not frames:
        return None
    rgb = np.concatenate([f.reshape(-1, 3) for f in frames])
    luma = rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    p1, p50, p99 = (float(np.percentile(luma, q)) for q in (1, 50, 99))
    mx, mn = rgb.max(axis=1), rgb.min(axis=1)
    lit = mx > 0.1
    sat = float(np.mean((mx[lit] - mn[lit]) / mx[lit])) if lit.any() else 0.0
    noise = []
    for f in frames:
        g = f @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        if g.shape[0] < 4 or g.shape[1] < 4:
            continue
        blur = (g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]) / 4.0
        diff = np.abs(g[1:-1, 1:-1] - blur)
        dark = g[1:-1, 1:-1] < 0.3
        if dark.sum() > 50:
            noise.append(float(np.median(diff[dark])))
    return {"p1": p1, "p50": p50, "p99": p99, "r": float(rgb[:, 0].mean()), "g": float(rgb[:, 1].mean()), "b": float(rgb[:, 2].mean()),
            "sat": sat, "noise": float(np.mean(noise)) if noise else 0.0}


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def plan(stats, strength="medium"):
    """The corrections for these statistics: {"gamma", "black", "white", "cast": (r, g, b), "saturation", "sharpen", "denoise", "notes"}.
    Every value is limited so a wrong measurement cannot ruin a clip."""
    s = STRENGTHS.get(strength, 1.0) if isinstance(strength, str) else float(strength)
    out = {"gamma": 1.0, "black": 0.0, "white": 1.0, "cast": (0.0, 0.0, 0.0), "saturation": 1.0, "sharpen": 0.0, "denoise": False, "notes": []}
    if not stats or s <= 0:
        return out
    med = _clamp(stats["p50"], 0.02, 0.98)
    # brightness: lift dark clips, tame very bright ones; at most gamma 1.7 (up) / 0.85 (down)
    if med < 0.34 or med > 0.66:
        full = math.log(med) / math.log(TARGET_MEDIAN)
        out["gamma"] = round(_clamp(1.0 + (full - 1.0) * 0.6 * s, 0.85, 1.7), 3)
        out["notes"].append("too dark, lifted" if out["gamma"] > 1 else "too bright, toned down")
    # contrast: stretch the black and white points when the range is narrow (flat or hazy picture)
    spread = stats["p99"] - stats["p1"]
    if spread < 0.60:                                       # ordinary phone footage spans about 0.1-0.9; only a really narrow range is "flat"
        black = _clamp(stats["p1"] - 0.01, 0.0, 0.12)
        white = _clamp(stats["p99"] + 0.03, 0.80, 1.0)
        out["black"], out["white"] = round(black * s, 3), round(1.0 - (1.0 - white) * s, 3)
        out["notes"].append("flat, contrast stretched")
    # colour cast: only a clear tint, in an averagely exposed scene, and never a saturated warm/cool look
    avg = (stats["r"] + stats["g"] + stats["b"]) / 3.0
    if avg > 0.08:
        dev = [(stats[c] / avg) - 1.0 for c in "rgb"]
        strong = max(abs(d) for d in dev)
        scenic = stats["sat"] > 0.38                               # a vivid scene (sunset, lake): the cast is the look
        if 0.10 < strong < 0.5 and not scenic and 0.2 < med < 0.8:
            out["cast"] = tuple(round(_clamp(-d * 0.5 * s, -0.06, 0.06), 3) for d in dev)
            out["notes"].append("colour cast reduced")
    if stats["sat"] < 0.16:
        out["saturation"] = round(1.0 + 0.25 * s, 3)
        out["notes"].append("dull, a little more colour")
    out["sharpen"] = round(0.35 * s, 2)
    if stats["noise"] > 0.012 and med < 0.3:
        out["denoise"] = True
        out["notes"].append("dark and noisy, light denoise")
    return out


def build_filter(p):
    """FFmpeg video filter chain for a plan, '' when nothing needs doing."""
    chain = []
    if p["denoise"]:
        chain.append("hqdn3d=2.5:2:3:3")
    if p["black"] > 0 or p["white"] < 1.0:
        chain.append(f"colorlevels=rimin={p['black']}:gimin={p['black']}:bimin={p['black']}:rimax={p['white']}:gimax={p['white']}:bimax={p['white']}")
    if abs(p["gamma"] - 1.0) > 0.02 or abs(p["saturation"] - 1.0) > 0.01:
        chain.append(f"eq=gamma={p['gamma']}:saturation={p['saturation']}")
    r, g, b = p["cast"]
    if any(abs(v) > 0.004 for v in (r, g, b)):
        chain.append(f"colorbalance=rm={r}:gm={g}:bm={b}")
    if p["sharpen"] > 0.05:
        chain.append(f"unsharp=5:5:{p['sharpen']}:5:5:0")
    return ",".join(chain)


def enhance_filter(video, strength="medium", ffmpeg=None, frames=None):
    """(filter chain, plan, stats) for a video file; the chain is '' when it needs nothing."""
    frames = frames if frames is not None else sample_frames(video, ffmpeg=ffmpeg)
    stats = measure(frames)
    p = plan(stats, strength)
    return build_filter(p), p, stats


def render(src, out, strength="medium", ffmpeg=None):
    """Write src with the corrections applied (audio copied). Returns the plan."""
    if ffmpeg is None:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    vf, p, _stats = enhance_filter(src, strength, ffmpeg)
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", src]
    if vf:
        cmd += ["-vf", vf]
    cmd += ["-c:v", "libx264", "-crf", "17", "-preset", "fast", "-pix_fmt", "yuv420p", "-c:a", "copy", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(out):
        raise RuntimeError("Could not enhance the video: " + (r.stderr or "")[-300:])
    return p
