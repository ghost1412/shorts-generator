"""A plan: the moments the analysis chose, written before any rendering so they can be reviewed and edited (`--plan_only`)."""
import json
import os

PLAN_FILE = "plan.json"


def write_plan(session_dir, highlights, source_video):
    """Write plan.json: one entry per moment (start, end, title, score, reason). Returns the path."""
    moments = []
    for i, h in enumerate(highlights, start=1):
        moments.append({
            "index": i, "start": round(float(h["start"]), 2), "end": round(float(h["end"]), 2),
            "title": str(h.get("title") or h.get("hook") or f"Moment {i}")[:120],
            "score": h.get("final_score", h.get("viral_score")), "reason": str(h.get("reason") or "")[:300],
        })
    path = os.path.join(session_dir, PLAN_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"source_video": source_video, "moments": moments}, f, ensure_ascii=False, indent=1)
    return path


def read_plan(session_dir):
    """The plan dict of a session, None when missing or unreadable."""
    try:
        with open(os.path.join(session_dir, PLAN_FILE), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data.get("moments"), list) else None
    except (OSError, ValueError, AttributeError):
        return None


def moments_text(moments):
    """`--moments` text for the kept moments, in time order: '420.0-465.5, 600.0-640.0'."""
    return ", ".join(f"{float(m['start']):.2f}-{float(m['end']):.2f}" for m in sorted(moments, key=lambda m: float(m["start"])))


_SHAPES = {"9:16": (270, 480), "1:1": (360, 360), "4:5": (384, 480)}


def framing_from_command(cmd):
    """(framing, aspect) a run will produce, from its saved command: framing is "crop", "fit" or None (landscape: the preview is the
    source as is). Game footage with automatic framing shows as a crop (the tool decides later)."""
    cmd = [str(x) for x in cmd or []]

    def value(flag, default=None):
        return cmd[cmd.index(flag) + 1] if flag in cmd and cmd.index(flag) + 1 < len(cmd) else default
    aspect = value("--aspect_ratio", "9:16")
    if value("--extract_mode", "shorts") == "long" or aspect not in _SHAPES:
        return None, aspect
    if value("--layout") == "fit" or value("--game_framing") == "fit":
        return "fit", aspect
    return "crop", aspect


def make_preview(source, start, end, out_path, height=360, framing=None, aspect="9:16"):
    """A small, fast preview clip (low resolution) of source[start:end] for reviewing a moment. Returns out_path, None on failure.
    With `framing` "crop" or "fit" the preview has the shape of the final short (centre crop, or the whole picture over a blurred
    copy); the real crop may follow a face, so this is an approximation. The original video is only read."""
    import shutil
    import subprocess
    exe = shutil.which("ffmpeg")
    if not exe:
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return None
    try:
        start, end = float(start), float(end)
    except (TypeError, ValueError):
        return None
    if end <= start or not os.path.isfile(str(source)):
        return None
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    shape = _SHAPES.get(aspect) if framing in ("crop", "fit") else None
    if shape and framing == "crop":
        w, h = shape
        filt = ["-vf", f"scale=-2:{h},crop={w}:{h}"]
    elif shape:
        w, h = shape
        filt = ["-filter_complex", f"[0:v]split=2[a][b];[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=15:2[bg];"
                                   f"[b]scale={w}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[v]", "-map", "[v]", "-map", "0:a?"]
    else:
        filt = ["-vf", f"scale=-2:{height}"]
    cmd = [exe, "-y", "-v", "error", "-ss", f"{start:.2f}", "-i", str(source), "-t", f"{end - start:.2f}",
           *filt, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-c:a", "aac", "-b:a", "96k", out_path]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=180)
    except (OSError, subprocess.SubprocessError):
        return None
    return out_path if r.returncode == 0 and os.path.isfile(out_path) else None
