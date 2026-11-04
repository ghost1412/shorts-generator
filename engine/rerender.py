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


def rerender_clip(session_dir, clip_index, start=None, end=None, caption_style=None, use_brand=True, cuts=None):
    """Re-render a clip in place. Returns the updated clip dict (from results.json).

    `cuts` = [(start, end)] spans of the ORIGINAL video (seconds) to remove from the clip (click-to-cut words).
    None keeps the cuts the clip already has, [] clears them."""
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

    if settings.get("caption_lang"):      # the run translated its captions: keep using that transcript
        from engine.caption_translate import resolve_language
        translated = os.path.join(session_dir, f"transcript_{resolve_language(settings['caption_lang'])}.json")
        if os.path.exists(translated):
            transcript = translated

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

    cuts = [tuple(c) for c in (clip.get("cuts") or [])] if cuts is None else [tuple(c) for c in cuts]
    extra = {}
    if settings.get("filler_video"):
        extra["filler_video"] = settings["filler_video"]
    tighten_mode = settings.get("tighten_mode", "cut")
    if cuts:
        from engine.fillers import MIN_KEEP, carve
        silence = carve(silence or [(start, end)], sorted(cuts), min_keep=MIN_KEEP)
        left = sum(min(b, end) - max(a, start) for a, b in silence if min(b, end) > max(a, start))
        if left < MIN_SECONDS:
            raise ValueError("Cutting those words would leave less than 3 seconds. Untick some of them.")
        tighten_mode = "cut"                       # cutting words always removes the picture too
        extra["remove_fillers"] = True             # tight padding, so a short cut is not stitched back together

    if settings.get("remove_fillers") and not cuts:
        # --remove_fillers: cut the ums again (the cut list for the window is not stored, so find them from the words)
        try:
            from engine.fillers import remove_fillers as find_fillers
            segs = _load_json(os.path.join(session_dir, "transcript.json"), {}).get("segments", [])
            total = max([s_.get("end", 0) for s_ in segs] or [0]) + 1.0
            silence, n_fill = find_fillers(silence or [], segs, total)
            extra["remove_fillers"] = True
            print(f"[Log] Removing {n_fill} filler word(s) again")
        except Exception as e:
            print(f"[Warning] Filler removal skipped on re-render: {e}")
    if settings.get("video_filter"):
        extra["video_filter"] = settings["video_filter"]       # the colour grade stays
    from engine.video_gen import extract_segments
    window = {"start": start, "end": end}
    hook_on = bool(settings.get("hook_overlay") and clip.get("hook"))
    if hook_on:
        window["hook_text"] = clip["hook"]           # --hook_overlay: the same title again
    tmp = tempfile.mkdtemp(prefix="rerender_", dir=session_dir)
    prev_hook_env = os.environ.get("SHORTSFLOW_HOOK_OVERLAY")
    if hook_on:
        os.environ["SHORTSFLOW_HOOK_OVERLAY"] = "1"
    zoom_on = bool(settings.get("auto_zoom"))        # --auto_zoom: the same punch-ins again
    prev_zoom_env = os.environ.get("SHORTSFLOW_AUTO_ZOOM")
    if zoom_on:
        os.environ["SHORTSFLOW_AUTO_ZOOM"] = "1"
    from engine import auto_edit
    edit_cfg = auto_edit.cfg_from_settings(settings)  # --auto_edit: the same zoom strength and sound effects again
    prev_zoom_strength = (os.environ.get("SHORTSFLOW_ZOOM_INTENSITY"), os.environ.get("SHORTSFLOW_ZOOM_SPACING"))
    if edit_cfg:
        os.environ["SHORTSFLOW_ZOOM_INTENSITY"] = str(edit_cfg["zoom_intensity"])
        os.environ["SHORTSFLOW_ZOOM_SPACING"] = str(edit_cfg["zoom_spacing"])
        os.environ["SHORTSFLOW_ZOOM_FILL"] = "1"
    emoji_on = bool(settings.get("caption_emoji"))    # --caption_emoji: the same keyword emoji again
    prev_emoji_env = os.environ.get("SHORTSFLOW_CAPTION_EMOJI")
    if emoji_on:
        os.environ["SHORTSFLOW_CAPTION_EMOJI"] = "1"
    caption_color = settings.get("caption_color")     # --caption_color: same accent colour again
    prev_color_env = os.environ.get("SHORTSFLOW_CAPTION_COLOR")
    if caption_color:
        os.environ["SHORTSFLOW_CAPTION_COLOR"] = caption_color
    try:
        files = extract_segments(
            source, [window], transcript, tmp, mode=mode, bitrate="12M", preset="medium", codec="libx264",
            interest_points=interest, silence_intervals=silence, tighten_mode=tighten_mode,
            use_remotion=bool(settings.get("use_remotion")), orientation=detect_orientation(source) if settings.get("smart_crop") else "landscape",
            letterbox_crop=detect_letterbox(source) if settings.get("smart_crop") else None,
            caption_style=style, subtitle_y_pos=settings.get("subtitle_y_pos", 1150), layout=settings.get("layout", "single"), **extra)
        if not files or not os.path.exists(files[0]):
            raise RuntimeError("The re-render produced no video.")
        new_clip = files[0]
        broll_events = []                            # cutaway times, for the auto-edit sound effects
        if settings.get("broll"):                    # --broll: the cutaways go back on (timing from the same retimed words as the captions)
            from engine.broll import apply_to_clip, clip_words
            try:
                with open(os.path.join(session_dir, "transcript.json"), "r", encoding="utf-8") as f_t:
                    broll_words = clip_words(json.load(f_t), start, end, silence, tighten_mode=tighten_mode,
                                             remove_fillers=bool(extra.get("remove_fillers")))
                if broll_words is not None:
                    apply_to_clip(new_clip, broll_words, layout=settings.get("layout", "single"),
                                  caption_y=settings.get("subtitle_y_pos", 1150) if settings.get("use_remotion") else 1150,
                                  hook_overlay=hook_on, events=broll_events)
            except (OSError, ValueError) as e:
                print(f"[Warning] B-roll skipped on re-render: {e}")
        if settings.get("clean_audio"):              # --clean_audio: a re-render must not fall back to the raw sound
            from engine.audio_clean import clean_audio
            clean_audio(new_clip)
        cold_info = None
        if settings.get("cold_open"):                # --cold_open: the best line goes first again
            try:
                from engine.broll import clip_words
                from engine.cold_open import apply_to_clip as apply_cold_open
                with open(os.path.join(session_dir, "transcript.json"), "r", encoding="utf-8") as f_t:
                    cold_words = clip_words(json.load(f_t), start, end, silence, tighten_mode=tighten_mode,
                                            remove_fillers=bool(extra.get("remove_fillers")))
                if cold_words is not None:
                    cold_info = apply_cold_open(new_clip, cold_words, hint=clip.get("hook"))
            except (OSError, ValueError) as e:
                print(f"[Warning] Cold open skipped on re-render: {e}")
        edit_log = None
        if edit_cfg:                                 # sound effects under the edits, and the summary for the review card
            from engine import sfx_mix
            from engine.broll import _ffmpeg, _probe
            zooms = auto_edit.read_zoom_moments(new_clip) if zoom_on else []
            events = auto_edit.build_sfx_events(edit_cfg, zooms, broll_events, cold_info)
            mixed = sfx_mix.mix_events(new_clip, events, volume_db=edit_cfg["sfx_db"]) if events else []
            try:
                length = _probe(new_clip, _ffmpeg())[2]
            except Exception:
                length = 0.0
            edit_log = {"tightened": bool(settings.get("tighten")), "zooms": len(zooms), "broll": len(broll_events),
                        "cold_open": float(cold_info["duration"]) if cold_info else 0.0, "sfx": len(mixed), "sfx_events": mixed,
                        "grade": settings.get("video_filter"), "captions": style if settings.get("use_remotion") else None,
                        "rhythm": auto_edit.rhythm(zooms, broll_events, cold_info, length) if length else {}}
            edit_log["summary"] = auto_edit.summarize(edit_log)
        brand_json = settings.get("brand")
        if use_brand and brand_json and not os.path.exists(brand_json):
            brand_json = None
        if use_brand and (brand_json or any(settings.get(k) for k in ("logo", "handle", "end_card"))):
            from engine.branding import apply_brand, load_brand
            try:
                # the brand file plus the --logo / --handle / --end_card given on the command line
                brand = load_brand(path=brand_json, logo=settings.get("logo"), handle=settings.get("handle"),
                                   end_card=settings.get("end_card"))
            except (OSError, ValueError) as e:
                print(f"[Warning] Brand kit skipped on re-render: {e}")
                brand = None
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
        if hook_on:
            if prev_hook_env is None:
                os.environ.pop("SHORTSFLOW_HOOK_OVERLAY", None)
            else:
                os.environ["SHORTSFLOW_HOOK_OVERLAY"] = prev_hook_env
        if zoom_on:
            if prev_zoom_env is None:
                os.environ.pop("SHORTSFLOW_AUTO_ZOOM", None)
            else:
                os.environ["SHORTSFLOW_AUTO_ZOOM"] = prev_zoom_env
        if edit_cfg:
            for key, old in zip(("SHORTSFLOW_ZOOM_INTENSITY", "SHORTSFLOW_ZOOM_SPACING"), prev_zoom_strength):
                if old is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old
        if emoji_on:
            if prev_emoji_env is None:
                os.environ.pop("SHORTSFLOW_CAPTION_EMOJI", None)
            else:
                os.environ["SHORTSFLOW_CAPTION_EMOJI"] = prev_emoji_env
        if caption_color:
            if prev_color_env is None:
                os.environ.pop("SHORTSFLOW_CAPTION_COLOR", None)
            else:
                os.environ["SHORTSFLOW_CAPTION_COLOR"] = prev_color_env

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
    clip["previous"] = {k: clip.get(k) for k in ("start", "end", "duration", "caption_style", "cuts")}
    clip.update({"start": round(start, 2), "end": round(end, 2),
                 "duration": round(end - start + (cold_info or {}).get("duration", 0), 2), "caption_style": style})
    if cold_info:
        clip["cold_open"] = cold_info
    else:
        clip.pop("cold_open", None)
    if edit_log:
        clip["edit"], clip["edit_summary"] = edit_log, edit_log["summary"]
    if cuts:
        clip["cuts"] = [[round(s, 3), round(e, 3)] for s, e in cuts]
    else:
        clip.pop("cuts", None)
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


def _utf8_console():
    """Progress lines contain emoji; a cp1252 pipe (Windows, redirected output) would turn them into a failed re-render."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def main(argv=None):
    _utf8_console()
    p = argparse.ArgumentParser(description="Re-render one clip with another caption style and/or trim window.")
    p.add_argument("session_dir")
    p.add_argument("clip_index", type=int)
    p.add_argument("--start", type=float)
    p.add_argument("--end", type=float)
    p.add_argument("--style", choices=["HORMOZI", "GLOW_BOX", "BOUNCE", "MINIMAL", "KARAOKE", "NEON", "BAR"])
    p.add_argument("--no-brand", action="store_true")
    p.add_argument("--cuts", help="spans of the original video to cut out, '1.2:1.8,3:3.5' (seconds); '' clears the cuts")
    a = p.parse_args(argv)
    try:
        cuts = None
        if a.cuts is not None:
            from shortsflow.word_edit import parse_spans_arg
            cuts = parse_spans_arg(a.cuts)
        clip = rerender_clip(a.session_dir, a.clip_index, a.start, a.end, a.style, use_brand=not a.no_brand, cuts=cuts)
    except (ValueError, RuntimeError) as e:
        print(f"[Error] {e}")
        return 1
    print(f"[Log] SUCCESS! Re-rendered clip {a.clip_index}: {clip['start']}s - {clip['end']}s ({clip['caption_style']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
