"""`--clip_report [md|csv|both]`: a summary of one clipping run (title, time range, score label, file, thumbnail)
written next to the clips, as `clip_report.md` and/or `clip_report.csv`."""
import csv
import os

FORMATS = ("md", "csv", "both")
COLUMNS = ("clip", "title", "start", "end", "duration_s", "score", "label", "hook", "file", "thumbnail")


def _label(score):
    from shortsflow.review import score_label
    return score_label(score)


def clock(seconds):
    """63.4 -> '1:03', 3725 -> '1:02:05'; '' for a missing value."""
    try:
        s = int(round(float(seconds)))
    except (TypeError, ValueError):
        return ""
    h, rem = divmod(max(s, 0), 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def _rel(path, base):
    if not path:
        return ""
    try:
        return os.path.relpath(path, base).replace("\\", "/") if os.path.isabs(path) or os.path.exists(path) else path.replace("\\", "/")
    except ValueError:  # another drive on Windows
        return path.replace("\\", "/")


def build_rows(highlights, files, meta, session_dir):
    """One dict per clip, in COLUMNS order, from the pipeline's own lists (highlights, rendered files, metadata)."""
    rows = []
    for i, h in enumerate(highlights):
        m = meta[i] if i < len(meta) else {}
        clip_path = files[i] if i < len(files) else ""
        thumb = m.get("thumbnail") or ""
        if thumb and clip_path and not os.path.isabs(thumb):
            thumb = os.path.join(os.path.dirname(clip_path), thumb)
        start, end = h.get("start"), h.get("end")
        try:
            duration = round(float(end) - float(start), 1)
        except (TypeError, ValueError):
            duration = ""
        score = h.get("viral_score")
        rows.append({
            "clip": i + 1,
            "title": (m.get("title") or h.get("hook_text") or f"Clip {i + 1}").strip(),
            "start": clock(start), "end": clock(end), "duration_s": duration,
            "score": "" if score is None else score, "label": _label(score),
            "hook": (h.get("hook_text") or "").strip(),
            "file": _rel(clip_path, session_dir), "thumbnail": _rel(thumb, session_dir),
        })
    return rows


def _md_cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def to_markdown(rows, source=""):
    lines = ["# Clip report", ""]
    if source:
        lines += [f"Source: `{source}`", ""]
    lines += [f"{len(rows)} clip(s).", ""]
    lines += ["| # | Title | Time | Score | File | Thumbnail |", "| --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        score = f"{r['label']} ({r['score']})" if r["score"] != "" else r["label"]
        lines.append(f"| {r['clip']} | {_md_cell(r['title'])} | {r['start']}-{r['end']} ({r['duration_s']} s) | {score} | "
                     f"{_md_cell(r['file'])} | {_md_cell(r['thumbnail'])} |")
    return "\n".join(lines) + "\n"


def write_report(rows, session_dir, fmt="md", source=""):
    """Write the report(s) into `session_dir`; returns the list of paths written."""
    if fmt not in FORMATS:
        raise ValueError(f"--clip_report must be one of {', '.join(FORMATS)} (got '{fmt}').")
    written = []
    if fmt in ("md", "both"):
        path = os.path.join(session_dir, "clip_report.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(to_markdown(rows, source))
        written.append(path)
    if fmt in ("csv", "both"):
        path = os.path.join(session_dir, "clip_report.csv")
        with open(path, "w", encoding="utf-8-sig", newline="") as f:  # BOM so Excel reads non-ASCII titles
            w = csv.DictWriter(f, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows(rows)
        written.append(path)
    return written
