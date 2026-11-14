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


def make_preview(source, start, end, out_path, height=360):
    """A small, fast preview clip (low resolution) of source[start:end] for reviewing a moment. Returns out_path, None on failure.
    The original video is only read."""
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
    cmd = [exe, "-y", "-v", "error", "-ss", f"{start:.2f}", "-i", str(source), "-t", f"{end - start:.2f}",
           "-vf", f"scale=-2:{height}", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-c:a", "aac", "-b:a", "96k", out_path]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=180)
    except (OSError, subprocess.SubprocessError):
        return None
    return out_path if r.returncode == 0 and os.path.isfile(out_path) else None
