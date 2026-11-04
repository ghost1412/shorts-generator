"""Helpers behind the clip review screen: read a finished run, label scores, bundle the kept clips.

A run is described by the `--output_json` file the clipper writes (clip_index, video_path, start, end, duration, viral_score,
hook, reason, title, description, tags, thumbnail).
"""
import json
import os
import zipfile


def score_label(score):
    """Plain-language label for a 0-100 virality score."""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "unrated"
    if s >= 80:
        return "strong"
    if s >= 60:
        return "good"
    if s >= 40:
        return "okay"
    return "weak"


def load_results(json_path):
    """Clip cards (dicts) from a results file; missing files and bad rows are skipped, paths are made absolute."""
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    base = os.path.dirname(os.path.abspath(json_path))
    settings = data.get("settings") or {}
    cards = []
    for i, c in enumerate(data.get("clips") or [], start=1):
        video = c.get("video_path") or ""
        if video and not os.path.isabs(video):
            # the command line writes paths relative to where it ran (and may mix / and \): try the likely bases, then the bare name
            name = os.path.basename(video.replace("\\", "/"))
            candidates = [os.path.join(base, video), os.path.join(os.path.dirname(base), video), os.path.abspath(video),
                          os.path.join(base, name)]
            video = next((p for p in candidates if os.path.exists(p)), candidates[0])
        if not video or not os.path.exists(video):
            continue
        thumb = c.get("thumbnail") or ""
        if thumb and not os.path.isabs(thumb):
            thumb = os.path.join(os.path.dirname(video), os.path.basename(thumb))
        score = c.get("viral_score")
        cards.append({
            "index": c.get("clip_index") or i,
            "video": video,
            "thumbnail": thumb if thumb and os.path.exists(thumb) else None,
            "title": (c.get("title") or f"Clip {i}").strip(),
            "description": (c.get("description") or "").strip(),
            "tags": [str(t) for t in (c.get("tags") or [])],
            "title_variants": [v for v in (c.get("title_variants") or []) if isinstance(v, dict) and v.get("title")],
            "hook": (c.get("hook") or "").strip(),
            "reason": (c.get("reason") or "").strip(),
            "edit_summary": (c.get("edit_summary") or "").strip(),
            "score": score,
            "label": score_label(score),
            "start": c.get("start"),
            "end": c.get("end"),
            "duration": c.get("duration"),
            "session_dir": base,
            "results_path": os.path.abspath(json_path),
            "caption_style": c.get("caption_style") or settings.get("caption_style") or "HORMOZI",
            "animated_captions": bool(settings.get("use_remotion")),
            "cuts": [tuple(x) for x in (c.get("cuts") or [])],
            "can_rerender": bool(settings and data.get("source_video")),
        })
    return cards


def card_text(card):
    """Copy-paste text for posting: title, description and hashtags."""
    tags = " ".join("#" + t.lstrip("#").replace(" ", "") for t in card.get("tags") or [])
    parts = [card.get("title", ""), card.get("description", ""), tags]
    return "\n\n".join(p for p in parts if p)


def variants_text(card):
    """Copy-ready list of the alternative titles ('[Curiosity] ...' per line); empty when there are none."""
    from engine.title_variants import variants_text as _vt
    return _vt(card.get("title_variants"))


def platform_texts(card):
    """{'tiktok': ..., 'instagram': ..., 'youtube': ...} caption/description text cut to each platform's limits."""
    from engine.platform_limits import LIMITS, fit_for_platform
    return {p: fit_for_platform(p, card.get("title", ""), card.get("description", ""), card.get("tags")) for p in LIMITS}


def safe_name(text, fallback="clip"):
    keep = "".join(ch if ch.isalnum() or ch in " -_" else "" for ch in (text or "")).strip()
    return (keep[:50].strip().replace(" ", "_")) or fallback


def build_zip(cards, dest_zip):
    """Zip the given clips (video, thumbnail and a .txt with title/description/tags). Returns the zip path or None when empty."""
    if not cards:
        return None
    os.makedirs(os.path.dirname(os.path.abspath(dest_zip)), exist_ok=True)
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_STORED) as z:     # videos are already compressed
        for n, c in enumerate(cards, start=1):
            stem = f"{n:02d}_{safe_name(c.get('title'))}"
            z.write(c["video"], f"{stem}.mp4")
            if c.get("thumbnail"):
                z.write(c["thumbnail"], f"{stem}.jpg")
            extra = f"\n\nOther title ideas:\n{variants_text(c)}" if c.get("title_variants") else ""
            z.writestr(f"{stem}.txt", card_text(c) + extra)
    return dest_zip


def run_label(folder_name, results_path):
    """Readable name for a run folder like web_20261103_120000: '3 Nov 2026, 12:00 - 2 shorts' (falls back to the folder name)."""
    import re
    import time
    m = re.search(r"(\d{8})_(\d{6})", folder_name)
    when = folder_name
    if m:
        try:
            t = time.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
            when = f"{t.tm_mday} {time.strftime('%b %Y, %H:%M', t)}"
        except ValueError:
            pass
    try:
        with open(results_path, encoding="utf-8") as f:
            n = len(json.load(f).get("clips") or [])
        return f"{when} - {n} short{'s' if n != 1 else ''}"
    except (OSError, ValueError):
        return when


def recent_runs(root, limit=15):
    """[(label, results_json_path)] for earlier runs under <root>/sessions, newest first."""
    out = []
    sessions = os.path.join(root, "sessions")
    if not os.path.isdir(sessions):
        return out
    for name in os.listdir(sessions):
        path = os.path.join(sessions, name, "results.json")
        if os.path.exists(path):
            out.append((os.path.getmtime(path), name, path))
    out.sort(reverse=True)
    return [(run_label(name, path), path) for _, name, path in out[:limit]]
