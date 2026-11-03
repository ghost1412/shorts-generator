"""Re-render ONE clip of a finished run with another caption style and/or a different start/end.

Uses the run's cached transcript, interest points and silence intervals (no re-transcription, no re-scoring) and the settings the run
stored in results.json. The previous version is kept next to the clip as <name>.previous.mp4 so a change can be undone.

    python -m engine.rerender SESSION_DIR CLIP_INDEX [--start S] [--end E] [--style GLOW_BOX] [--no-brand]
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

MIN_SECONDS = 3.0
MAX_SECONDS = 180.0


def _load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _clip_file(session_dir, clip):
    """Absolute path of a clip's video: results.json stores it relative to wherever the run started."""
    path = clip.get("video_path") or ""
    if os.path.isabs(path) and os.path.exists(path):
        return path
    for candidate in (os.path.abspath(path), os.path.join(session_dir, os.path.basename(path.replace("\\", "/")))):
        if os.path.exists(candidate):
            return candidate
    return os.path.join(session_dir, os.path.basename(path.replace("\\", "/")))


def validate_window(start, end, source_seconds=None):
    """(start, end) as floats, or ValueError with a plain-language reason."""
    try:
        start, end = float(start), float(end)
    except (TypeError, ValueError):
        raise ValueError("Start and end must be numbers of seconds.")
    if start < 0:
        raise ValueError("The start cannot be before the beginning of the video.")
    if end - start < MIN_SECONDS:
        raise ValueError(f"A short must be at least {MIN_SECONDS:.0f} seconds long.")
    if end - start > MAX_SECONDS:
        raise ValueError(f"A short can be at most {MAX_SECONDS:.0f} seconds long.")
    if source_seconds and end > source_seconds + 0.5:
        raise ValueError(f"The end is past the end of the video ({source_seconds:.0f} s).")
    return start, end


def rerender_clip(session_dir, clip_index, start=None, end=None, caption_style=None, use_brand=True):
    """Re-render a clip in place. Returns the updated clip dict (from results.json)."""
    results_path = os.path.join(session_dir, "results.json")
    data = _load_json(results_path, None)
    if not data:
        raise ValueError("This run has no results.json, so it cannot be re-rendered.")
    clip = next((c for c in data.get("clips", []) if int(c.get("clip_index", 0)) == int(clip_index)), None)
    if clip is None:
        raise ValueError(f"There is no clip {clip_index} in this run.")
    settings = data.get("settings") or {}
    source = data.get("source_video")
    if not source or not os.path.exists(source):
        raise ValueError("The original video is no longer where it was, so the clip cannot be re-rendered.")
    transcript = os.path.join(session_dir, "transcript.json")
    if not os.path.exists(transcript):
        raise ValueError("The saved transcript for this run is missing.")

    from engine.analysis import detect_letterbox, detect_orientation, probe_duration
    start, end = validate_window(clip["start"] if start is None else start, clip["end"] if end is None else end, probe_duration(source))
    style = caption_style or settings.get("caption_style") or "HORMOZI"
    mode = settings.get("extract_mode", "shorts")

    interest = None
    if settings.get("smart_crop"):
        from engine.analysis import detect_interest_points
        raw = _load_json(os.path.join(session_dir, "interest_points.json"), {})
        interest = {float(k): v for k, v in raw.items()}
        covered = [t for t in interest if start <= t <= end]
        if len(covered) < max(2, int((end - start) / 5)):       # the window moved outside what was analysed: analyse just this window
            interest.update(detect_interest_points(source, segments=[(start, end)]))
    silence = None
    if settings.get("tighten"):
        silence = [tuple(item) for item in _load_json(os.path.join(session_dir, "silence_intervals.json"), [])]

    from engine.video_gen import extract_segments
    tmp = tempfile.mkdtemp(prefix="rerender_", dir=session_dir)
    try:
        files = extract_segments(
            source, [{"start": start, "end": end}], transcript, tmp, mode=mode, bitrate="12M", preset="medium", codec="libx264",
            interest_points=interest, silence_intervals=silence, tighten_mode=settings.get("tighten_mode", "cut"),
            use_remotion=bool(settings.get("use_remotion")), orientation=detect_orientation(source) if settings.get("smart_crop") else "landscape",
            letterbox_crop=detect_letterbox(source) if settings.get("smart_crop") else None,
            caption_style=style, subtitle_y_pos=settings.get("subtitle_y_pos", 1150), layout=settings.get("layout", "single"))
        if not files or not os.path.exists(files[0]):
            raise RuntimeError("The re-render produced no video.")
        new_clip = files[0]
        brand_json = settings.get("brand")
        if use_brand and brand_json and os.path.exists(brand_json):
            from engine.branding import apply_brand, load_brand
            brand = load_brand(path=brand_json)
            if brand:
                apply_brand(new_clip, brand)

        target = _clip_file(session_dir, clip)
        previous = os.path.splitext(target)[0] + ".previous.mp4"
        if os.path.exists(previous):
            os.remove(previous)
        if os.path.exists(target):
            shutil.move(target, previous)
        shutil.move(new_clip, target)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    thumb = clip.get("thumbnail")
    if thumb and not os.path.isabs(thumb):
        thumb = os.path.join(os.path.dirname(target), os.path.basename(thumb))
    if thumb:
        try:
            from engine.video_gen import generate_thumbnail_with_badge
            generate_thumbnail_with_badge(target, thumb, badge_text="VIRAL MOMENT", at_time=1.5)
        except Exception as e:
            print(f"[Warning] Thumbnail not refreshed: {e}")

    # remember what the clip looked like so "undo" can put the numbers back together with the video
    clip["previous"] = {k: clip.get(k) for k in ("start", "end", "duration", "caption_style")}
    clip.update({"start": round(start, 2), "end": round(end, 2), "duration": round(end - start, 2), "caption_style": style})
    tmp_json = results_path + ".tmp"
    with open(tmp_json, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    os.replace(tmp_json, results_path)
    return clip


def undo_rerender(session_dir, clip_index):
    """Put the previous version of a clip back. Returns True when there was one."""
    results_path = os.path.join(session_dir, "results.json")
    data = _load_json(results_path, None) or {}
    clip = next((c for c in data.get("clips", []) if int(c.get("clip_index", 0)) == int(clip_index)), None)
    if not clip:
        return False
    target = _clip_file(session_dir, clip)
    previous = os.path.splitext(target)[0] + ".previous.mp4"
    if not os.path.exists(previous):
        return False
    os.replace(previous, target)
    before = clip.pop("previous", None)
    if before:
        for key, value in before.items():
            if value is None:
                clip.pop(key, None)
            else:
                clip[key] = value
    tmp_json = results_path + ".tmp"
    with open(tmp_json, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    os.replace(tmp_json, results_path)
    return True


def main(argv=None):
    p = argparse.ArgumentParser(description="Re-render one clip with another caption style and/or trim window.")
    p.add_argument("session_dir")
    p.add_argument("clip_index", type=int)
    p.add_argument("--start", type=float)
    p.add_argument("--end", type=float)
    p.add_argument("--style", choices=["HORMOZI", "GLOW_BOX", "BOUNCE", "MINIMAL"])
    p.add_argument("--no-brand", action="store_true")
    a = p.parse_args(argv)
    try:
        clip = rerender_clip(a.session_dir, a.clip_index, a.start, a.end, a.style, use_brand=not a.no_brand)
    except (ValueError, RuntimeError) as e:
        print(f"[Error] {e}")
        return 1
    print(f"[Log] SUCCESS! Re-rendered clip {a.clip_index}: {clip['start']}s - {clip['end']}s ({clip['caption_style']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
