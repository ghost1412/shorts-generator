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
