#!/usr/bin/env python3
"""
ShortsFlow AI Studio - Browser WebUI (Gradio)
Runs locally, in Docker, on Google Colab or on Hugging Face Spaces.

    python webui.py               # http://localhost:7860
    python webui.py --share       # public gradio.live link (Colab)
"""

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys

import gradio as gr

from shortsflow import web_args

try:  # checkout: the repo; pip install: the workspace folder `shortsflow` sets in SHORTSFLOW_HOME
    from engine.paths import project_root
    ROOT = project_root()
except Exception:
    ROOT = os.path.dirname(os.path.abspath(__file__))


def tolerate_missing_ffprobe():
    """Gradio's video player runs `ffprobe` to check playability whenever `ffmpeg` is on the PATH, and crashes the page if only
    ffmpeg is there (pip installs expose the bundled ffmpeg but have no ffprobe). Our clips are plain H.264 MP4, which browsers
    play, so skip that check when ffprobe is missing."""
    if shutil.which("ffprobe"):
        return False
    try:
        from gradio import processing_utils
        processing_utils.video_is_playable = lambda *args, **kwargs: True
        return True
    except Exception:
        return False


def _gradio_major():
    try:
        return int(gr.__version__.split(".")[0])
    except Exception:
        return 5


def _app_theme():
    """One calm, professional look: system fonts (nothing is fetched from the internet), slate neutrals, an orange accent, rounded cards."""
    return gr.themes.Soft(primary_hue="orange", secondary_hue="orange", neutral_hue="slate",
                          font=("system-ui", "Segoe UI", "Helvetica Neue", "Arial", "sans-serif"),
                          radius_size=gr.themes.sizes.radius_lg, spacing_size=gr.themes.sizes.spacing_md).set(
        block_label_background_fill="transparent", block_label_text_color="*body_text_color", block_title_text_color="*body_text_color",     # plain labels, not coloured chips
        block_label_border_width="0px", block_label_shadow="none", block_label_text_weight="600",
        block_label_background_fill_dark="transparent", block_label_text_color_dark="*body_text_color", block_label_border_width_dark="0px")


def _blocks_theme():
    """Gradio 5 takes the theme in gr.Blocks(); Gradio 6 moved it to launch()."""
    return {} if _gradio_major() >= 6 else {"theme": _app_theme()}


def _launch_theme():
    return {"theme": _app_theme()} if _gradio_major() >= 6 else {}


def _pipeline_cmd():
    """Command prefix that runs the pipeline: main.py in a checkout, `python -m shortsflow` in a pip install."""
    if os.path.exists(os.path.join(ROOT, "main.py")):
        return [sys.executable, "main.py"]
    return [sys.executable, "-m", "shortsflow"]

GENERATE_MODES = [
    "AUTO", "FACTS", "STORY", "EXPLAINER", "WYR", "TOP_5", "CHAT_STORY", "HORROR",
    "TRUE_CRIME", "REDDIT", "TRIVIA", "QUOTE", "RIDDLE", "EMOJI_GUESS", "ODD_ONE_OUT",
    "NEWS", "BIBLE", "ARTICLE", "UGC", "FUNNY_EXPLAINER",
]
CAPTION_STYLES = ["HORMOZI", "GLOW_BOX", "BOUNCE", "MINIMAL", "KARAOKE", "NEON", "BAR", "MARKER", "SOFT", "WORDCUT", "NEGATIVE", "HANDWRITTEN", "SIMPLE", "TYPEWRITER", "AUTO", "RANDOM"]
VIBES = ["suspense", "spooky", "cinematic", "upbeat", "sarcastic", "funny"]
ASPECTS = ["9:16", "16:9", "1:1", "4:5"]
LLM_PROVIDERS = ["auto", "gemini", "ollama", "openai", "anthropic", "deepseek", "groq", "openrouter"]


def _snapshot_videos():
    """All rendered .mp4 files main.py may write (project root and sessions/)."""
    patterns = [os.path.join(ROOT, "*.mp4"), os.path.join(ROOT, "sessions*", "**", "*.mp4")]
    files = {}
    for pattern in patterns:
        for path in glob.glob(pattern, recursive=True):
            if "TEMP_MPY" in path or "temp_segments" in path or os.path.basename(path).startswith(("preview_", "scene_clip_", "temp_", "seg_")):
                continue
            files[path] = os.path.getmtime(path)
    return files


_JOBS = []          # pipeline processes started by this app, so the Stop button can end them
_STOPPED = set()    # process ids that were stopped on purpose (reported as "stopped", not as a failure)


def _kill_tree(proc):
    """End a pipeline process AND everything it started (FFmpeg, Node, the browser the animated captions use)."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)   # only this process tree
        else:
            import signal
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def stop_jobs():
    """Stop button: end every pipeline this app started. Whatever was already finished stays on disk."""
    running = [p for p in list(_JOBS) if p.poll() is None]
    for p in running:
        _STOPPED.add(p.pid)
        _kill_tree(p)
    if not running:
        return "Nothing is running right now."
    return ("⏹ Stopped. Whatever was already finished is kept: open “Earlier runs” → “Continue one that stopped” on the Start here tab "
            "to carry on from there.")


def _run(cmd):
    """Run main.py, streaming its log; yields (log, videos) and finally the new videos."""
    before = _snapshot_videos()
    log = f"$ {' '.join(cmd)}\n\n"
    yield log, []

    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    proc = subprocess.Popen(
        cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", env=env,
        **({"start_new_session": True} if os.name != "nt" else {}),
    )
    _JOBS.append(proc)
    try:
        for line in proc.stdout:
            log += line
            yield log[-20000:], []
        proc.wait()
    finally:
        if proc in _JOBS:
            _JOBS.remove(proc)

    after = _snapshot_videos()
    new = sorted(
        (p for p, m in after.items() if p not in before or m > before[p]),
        key=lambda p: after[p],
    )
    if proc.pid in _STOPPED:
        status = "⏹ Stopped"
    else:
        status = "✅ Done" if proc.returncode == 0 else f"❌ main.py exited with code {proc.returncode}"
    log += f"\n{status} - {len(new)} video(s) rendered.\n"
    yield log[-20000:], new


def _common_args(caption_style, aspect_ratio, use_remotion, llm_provider, tts_provider):
    args = ["--caption_style", caption_style, "--aspect_ratio", aspect_ratio,
            "--llm_provider", llm_provider, "--tts_provider", tts_provider, "--skip-upload"]
    if use_remotion:
        args.append("--use_remotion")
    return args


def _length(value, default=30):
    """Length of each short in seconds, kept between 10 and 60 (shorts are never longer than a minute)."""
    try:
        return max(10, min(60, int(float(value))))
    except (TypeError, ValueError):
        return default


def _minutes(value):
    """Highlights video length in whole minutes, at least 1 (the box can be left empty)."""
    try:
        return max(1, int(float(value)))
    except (TypeError, ValueError):
        return 4


def _count(value):
    """How many shorts: a whole number, at least 1 (the box can be left empty)."""
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 3


def kind_choices_with_none():
    from shortsflow.ui import kinds
    return [("No preset: my own settings", "")] + kinds.kind_choices()


def apply_kind(kind):
    """The values for (auto-edit style, game checkbox, picture, template, caption style, note) of a video kind; no change when empty."""
    from shortsflow.ui import kinds
    if not kind:
        return [gr.update()] * 5 + [""]
    k = kinds.settings_for(kind)
    return k["edit"], k["game"], k["framing"], k["template"], k["captions"], "✔ " + kinds.describe(kind)


def template_controls(prefix_info="", with_shape=True):
    """The look controls, shared by every flow (see shortsflow/ui/blocks.py). Returns the components in the order `clip_video` /
    `quick_clip` take them after their other options."""
    from shortsflow.ui.blocks import look_block
    return look_block(gr, web_args, prefix_info, with_shape)


def clip_video(url, upload, clip_count, target_duration, layout, smart_crop, tighten, broll, srt,
               caption_style, aspect_ratio, use_remotion, llm_provider, tts_provider,
               clean_audio=False, hook_overlay=False, caption_emoji=False, filler_video=None, auto_zoom=False, cold_open=False,
               spoken="en", auto_edit="none", edit_strength="medium", stat_pops=False,
               game=False, game_mix="0.5", caption_position="default", caption_size="default", game_framing="auto",
               visual_template="none", intro_animation="none", outro_animation="none",
               tpl_speaker="", tpl_role="", tpl_show="", tpl_handle="", tpl_headline="", tpl_cta=""):
    source = upload or (url or "").strip()
    if not source:
        raise gr.Error("Paste a YouTube link or upload a video file.")
    cmd = [*_pipeline_cmd(), "--source_video", source, "--extract_mode", "shorts",
           "--clip_count", str(_count(clip_count)), "--target_duration", str(int(target_duration)),
           "--layout", layout]
    for flag, on in (("--smart_crop", smart_crop), ("--tighten", tighten), ("--broll", broll), ("--srt", srt)):
        if on:
            cmd.append(flag)
    cmd += _common_args(caption_style, aspect_ratio, use_remotion, llm_provider, tts_provider)
    cmd += web_args.extras_args(clean_audio, hook_overlay, caption_emoji, use_remotion, auto_zoom=auto_zoom, cold_open=cold_open, stat_pops=stat_pops)
    cmd += web_args.filler_args(layout, filler_video)
    if spoken and spoken != "en":
        cmd += ["--language", spoken]            # the command line assumes English unless told otherwise
    cmd += web_args.edit_args(auto_edit, edit_strength)
    if use_remotion:
        cmd += web_args.caption_look_args(caption_position, caption_size)
    cmd += web_args.game_args(game, game_mix, game_framing)
    cmd += web_args.template_args(visual_template, intro_animation, outro_animation, tpl_speaker, tpl_role, tpl_show, tpl_handle, tpl_headline, tpl_cta)
    yield from _run(cmd)


def dub_video(upload, url, target_lang, spoken="auto", burn_captions=False, tts_provider="auto", voice="auto", original="music", resume=None, tone="faithful", delivery="neutral", llm_provider="auto", caption_size="default", caption_position="bottom"):
    """Dub tab: translate a video's speech and re-voice it. Yields (status, log, video, srt)."""
    import time
    from shortsflow import onboarding
    if resume:                                            # continue a dub that crashed or was stopped: same folder, saved translation and voices
        found = web_args.read_dub_session(resume)
        if not found:
            raise gr.Error("That earlier dub cannot be continued (its saved translation or video is missing). Start it again.")
        source, target_lang, _lines = found
        session = resume
    else:
        source = upload or (url or "").strip()
        if not source:
            raise gr.Error("Paste a video link or upload a video file first.")
        if not target_lang:
            raise gr.Error("Choose the language to dub into.")
        session = os.path.join(ROOT, "sessions", time.strftime("dub_%Y%m%d_%H%M%S"))
    os.makedirs(session, exist_ok=True)
    cmd = [*_pipeline_cmd(), *web_args.dub_args(source, target_lang, spoken, burn_captions, session, tts_provider, voice, original, tone, delivery, llm_provider, caption_size, caption_position)]
    progress, seen = onboarding.Progress(steps=onboarding.DUB_STEPS), 0
    status = progress.message
    yield status, "", None, None
    log = ""
    for log, _videos in _run(cmd):
        lines = log.splitlines()
        for line in lines[seen:]:
            status = progress.feed(line)
        seen = len(lines)
        yield status, log, None, None
    video, srt = web_args.find_dub_outputs(session)
    if video:
        name = {code: n for n, code in web_args.dub_languages()}.get(target_lang, target_lang)
        yield f"✅ Done! Your video dubbed into {name} is ready below.", log, video, srt
        return
    reason = next((ln.split("]", 1)[1].strip() for ln in reversed(log.splitlines()) if ln.startswith("[Error]")), "")
    yield "❌ No dubbed video was made." + (f" {reason}" if reason else " Open 'Technical details' for the reason."), log, None, None


def trip_recap(files, name, stops, note, hook, length, style, music, reuse="", drive="", look=False, both=False, name_places=True, enhance=False, kind="trip", keep_sound=False,
               grade="default", edit="none", edit_strength="medium", clean_sound=False, sample="auto", transitions="auto", subject_look="auto", subject_color="auto", subject_max=2, lines="", open_result=False, llm_provider="auto", steps=""):
    """Recap tab (trip, wedding, event, family): several videos in filming order -> one recap with a hook, title cards and an itinerary."""
    import time
    from shortsflow import reuse as _reuse
    if reuse and not files:
        files = [v for v in _reuse.trip_videos_of(reuse) if os.path.exists(v)]      # the earlier recap's videos
    if not files:
        raise gr.Error("Add your trip videos first (in the order you filmed them).")
    session = os.path.join(ROOT, "sessions", time.strftime("trip_%Y%m%d_%H%M%S"))
    os.makedirs(session, exist_ok=True)
    steps_file = None
    if (steps or "").strip():                       # a step-by-step video: the text box is the steps file
        steps_file = os.path.join(session, "steps.txt")
        with open(steps_file, "w", encoding="utf-8") as f:
            f.write(steps)
    cmd = [*_pipeline_cmd(), *web_args.trip_args(files, session, name, stops, note, hook, length, style, music, look=look, both=both, name_places=name_places, enhance=enhance, kind=kind, keep_sound=keep_sound,
                                                            grade=grade, edit=edit, edit_strength=edit_strength, clean_sound=clean_sound, sample=sample, transitions=transitions, subject_look=subject_look, subject_color=subject_color, subject_max=subject_max, lines=lines, open_result=open_result, llm_provider=llm_provider, steps_file=steps_file)]
    if reuse:
        copied = _reuse.seed_session(os.path.dirname(reuse), session, kind="trip")
        if copied:
            print(f"[Log] Reusing {len(copied)} saved result(s) from the earlier recap (picture descriptions, place names).")
    save_command(session, cmd)
    yield "Working on your recap...", "", None, None
    log = ""
    for log, _videos in _run(cmd):
        last = next((ln.split("]", 1)[1].strip() for ln in reversed(log.splitlines()) if ln.startswith("[Log]")), "")
        yield f"Working... {last}"[:200], log, None, None
    video, md = web_args.find_trip_outputs(session)
    if video:
        videos = web_args.find_trip_videos(session)
        downloads = ([md] if md else []) + (videos if len(videos) > 1 else [])          # the itinerary, and both versions when there are two
        done = "✅ Done! Your trip recap is ready below." + (" Both versions are in the download box." if len(videos) > 1 else "")
        yield done, log, video, downloads
        if (drive or "").strip():
            yield done + "\n\n☁️ Uploading to Google Drive...", log, video, downloads
            yield done + "\n\n" + drive_upload_message(videos, drive), log, video, downloads
        return
    reason = next((ln.split("]", 1)[1].strip() for ln in reversed(log.splitlines()) if ln.startswith("[Error]")), "")
    yield "❌ No recap was made." + (f" {reason}" if reason else " Open 'Technical details' for the reason."), log, None, None


def recap_kind_changed(kind):
    """Relabel the Recap form for the chosen kind; the place lookup only exists for trips, and the original sound defaults on for events."""
    name_label, parts_label, note_label = web_args.recap_kind_labels(kind)
    trip = kind in (None, "", "trip")
    return (gr.update(label=name_label), gr.update(label=parts_label), gr.update(label=note_label),
            gr.update(visible=trip, value=trip), gr.update(value=not trip))


def rate_clip(card, liked):
    """Thumbs up / down on a review card: saved locally; the picker learns which clip length you tend to like (engine/feedback.py)."""
    from engine import feedback
    n = feedback.record(card.get("title"), card.get("duration") or 0, card.get("score"), liked)
    if not n:
        return "Could not save the rating on this computer."
    return ("Thanks! " if liked else "Noted. ") + feedback.summary()


def photo_reel(files, reel_type, name="", texts="", music=None, duration=24):
    """Photo reel tab: photos in, a typed reel out. Yields (status, log, video)."""
    import time
    from shortsflow import onboarding
    from engine.photo_reel_types import PHOTO_EXTS
    photos = [f for f in (files or []) if str(getattr(f, "name", f)).lower().endswith(PHOTO_EXTS)]
    if len(photos) < 3:
        raise gr.Error("Add at least 3 photos (JPG, PNG or WebP).")
    session = os.path.join(ROOT, "sessions", time.strftime("reel_%Y%m%d_%H%M%S"))
    folder = web_args.stage_photos(photos, os.path.join(session, "photos"))
    cmd = [*_pipeline_cmd(), *web_args.photo_reel_args(folder, reel_type, name, texts, music, duration, session)]
    progress, seen = onboarding.Progress(start="📸 Looking at your photos...", steps=onboarding.PHOTO_STEPS), 0
    status = progress.message
    yield status, "", None
    log = ""
    for log, _videos in _run(cmd):
        lines = log.splitlines()
        for line in lines[seen:]:
            status = progress.feed(line)
        seen = len(lines)
        yield status, log, None
    video = web_args.find_photo_reel(session)
    if video:
        yield "✅ Done! Your reel is ready below.", log, video
        return
    reason = next((ln.split("]", 1)[1].strip() for ln in reversed(log.splitlines()) if ln.startswith("[Error]")), "")
    yield "❌ No reel was made." + (f" {reason}" if reason else " Open 'Technical details' for the reason."), log, None


def generate_short(mode, category, prompt, script, vibe, voice, caption_style, aspect_ratio,
                   use_remotion, llm_provider, tts_provider):
    cmd = [*_pipeline_cmd(), "--mode", mode, "--vibe", vibe]
    for flag, value in (("--category", category), ("--prompt", prompt), ("--script", script), ("--voice", voice)):
        if value and value.strip():
            cmd += [flag, value.strip()]
    cmd += _common_args(caption_style, aspect_ratio, use_remotion, llm_provider, tts_provider)
    yield from _run(cmd)


def setup_status():
    """Markdown checklist of what is ready on this machine (same checks as `shortsflow doctor`)."""
    from shortsflow import onboarding, workspace
    try:
        return onboarding.checklist_markdown(workspace.doctor(ROOT))
    except Exception as e:  # never break the page over a diagnostics problem
        return f"Could not check the setup automatically ({e})."


def save_llm_key(provider, key):
    """Save the key typed in the 'AI-written titles' box under the right name in .env."""
    from shortsflow import onboarding
    name = web_args.llm_key_env_name(provider)
    if not name:
        return "⚠️ Choose a provider first."
    label = web_args.LLM_KEY_PROVIDERS[provider][0]
    if onboarding.save_env_key(os.path.join(ROOT, ".env"), name, key):
        return f"✅ Saved. AI titles and descriptions can use your {label} key from the next run."
    return "⚠️ That does not look like a key. Copy it again from the provider's page (no spaces)."


def save_groq_key(key):
    return save_llm_key("groq", key)


def _cards_from_videos(videos):
    """Fallback cards when the run wrote no results.json: just the files, with generic titles."""
    return [{"index": i, "video": v, "thumbnail": None, "title": f"Short {i}", "description": "", "tags": [], "hook": "",
             "reason": "", "score": None, "label": "unrated", "start": None, "end": None, "duration": None}
            for i, v in enumerate(videos, start=1)]


CAPTION_CHOICES = [("Bold yellow (Hormozi)", "HORMOZI"), ("Pink glow box", "GLOW_BOX"),
                   ("Bouncy gold", "BOUNCE"), ("Clean dark boxes", "MINIMAL"),
                   ("Karaoke sweep", "KARAOKE"), ("Neon glow", "NEON"), ("Subtitle bar", "BAR"),
                   ("Marker sweep", "MARKER"), ("Soft build", "SOFT"), ("Word cut", "WORDCUT"), ("Keyword tone", "NEGATIVE"),
                   ("Handwritten", "HANDWRITTEN"), ("Simple", "SIMPLE"), ("Typewriter", "TYPEWRITER")]
SPOKEN_CHOICES = [("Detect it automatically", "auto"), ("English", "en"), ("Hindi", "hi"), ("Spanish", "es"), ("French", "fr"),
                  ("German", "de"), ("Portuguese", "pt"), ("Italian", "it"), ("Japanese", "ja"), ("Korean", "ko"),
                  ("Chinese", "zh"), ("Russian", "ru"), ("Arabic", "ar"), ("Turkish", "tr")]
try:
    from engine.caption_translate import LANGUAGES as CAPTION_LANGUAGES
except Exception:   # engine not importable yet in some installs: the same list, written out
    CAPTION_LANGUAGES = {"en": "English", "es": "Spanish", "fr": "French", "de": "German", "pt": "Portuguese", "it": "Italian",
                         "nl": "Dutch", "pl": "Polish", "tr": "Turkish", "id": "Indonesian", "vi": "Vietnamese",
                         "hi": "Hindi", "mr": "Marathi", "ru": "Russian", "uk": "Ukrainian", "bg": "Bulgarian", "el": "Greek",
                         "ar": "Arabic", "zh": "Chinese", "ja": "Japanese", "ko": "Korean"}
CAPTION_LANG_CHOICES = [("Same as the video (no translation)", "")] + [(name, code) for code, name in CAPTION_LANGUAGES.items()]
BRAND_POSITIONS = ["top-right", "top-left", "bottom-right", "bottom-left"]


def style_preview(style):
    """Path of the preview still for a caption style (None when the image is missing)."""
    path = os.path.join(ROOT, "assets", "caption_previews", f"{style}.jpg")
    return path if os.path.exists(path) else None


def brand_fields():
    """Saved brand -> values for the brand form."""
    from shortsflow import brand
    b = brand.load(ROOT)
    if not b:
        return "", "", brand.DEFAULT_COLOR, "top-right", None, "No brand saved yet."
    return (b["handle"], b["end_card"], b["color"], b["logo_position"], b["logo"],
            "Your brand is saved. It is added to every short while the box above is ticked.")


def save_brand(logo, handle, end_card, color, position):
    from shortsflow import brand
    try:
        return brand.save(ROOT, logo_path=logo, handle=handle, end_card=end_card, color=color, position=position)
    except ValueError as e:
        raise gr.Error(str(e))


def clear_brand():
    from shortsflow import brand
    brand.clear(ROOT)
    return "", "", brand.DEFAULT_COLOR, "top-right", None, "Brand removed."


def _range_too_long(text):
    """True when `text` is a start-end range longer than a short can be (the tool would silently cut it to a minute)."""
    from engine.moments import parse_time, MAX_SHORT
    m = re.fullmatch(r"(.+?)\s*[-–—]\s*(.+)", text.strip())
    if not m:
        return False
    try:
        return parse_time(m.group(2)) - parse_time(m.group(1)) > MAX_SHORT + 1
    except ValueError:
        return False


def quick_clip(url, upload, clip_count, captions, caption_style="HORMOZI", use_brand=True,
               logo=None, handle="", end_card="", color=None, position="top-right", mode="shorts", minutes=4, find="", cut="", spoken="auto", caption_lang="",
               clean_audio=False, hook_overlay=False, caption_emoji=False, filler=False, filler_video=None, broll=False, auto_zoom=False, cold_open=False,
               auto_edit="none", edit_strength="medium", stat_pops=False, length=30, moments="", about="", visual=False, reuse="", reuse_all="all", drive="", enhance=False, grade="default",
               game=False, game_mix="0.5", caption_position="default", caption_size="default", game_framing="auto", llm_provider="auto",
               visual_template="none", intro_animation="none", outro_animation="none",
               tpl_speaker="", tpl_role="", tpl_show="", tpl_handle="", tpl_headline="", tpl_cta="", shape="9:16", plan_first=False, between="", picture="auto"):
    """The beginner flow: a video in, shorts out, with plain-language progress instead of a raw log.
    Yields (status, log, cards): `cards` feeds the review screen."""
    import time
    source = upload or (url or "").strip()
    from shortsflow import reuse as _reuse
    if reuse and not source:
        source = _reuse.source_of(reuse)                  # the earlier run's video, so it does not have to be added again
    if not source:
        raise gr.Error("Paste a video link or upload a video file first.")
    session = os.path.join(ROOT, "sessions", time.strftime("web_%Y%m%d_%H%M%S"))
    results = os.path.join(session, "results.json")
    os.makedirs(session, exist_ok=True)
    long_form = mode == "long"
    if picture in ("fit", "crop") and game_framing == "auto":
        game_framing = picture                      # the one plain "Picture" choice also steers game footage
    layout = "split_filler" if filler else ("fit" if (game or picture == "fit") and not long_form else "auto")   # game footage: keep the whole picture
    lang_args = ["--language", (spoken or "auto")]
    if caption_lang:
        lang_args += ["--caption_lang", caption_lang]
    if long_form:   # one highlights video made of the best moments, in story order (landscape, like the source)
        cmd = [*_pipeline_cmd(), "--source_video", source, "--extract_mode", "long",
               "--target_duration", str(_minutes(minutes) * 60), "--skip-upload",
               "--session_dir", session, "--output_json", results]
        if captions:
            cmd += ["--reel_captions"]
        cmd += web_args.template_args(visual_template, intro_animation, outro_animation, tpl_speaker, tpl_role, tpl_show, tpl_handle, tpl_headline, tpl_cta)
    else:
        cmd = [*_pipeline_cmd(), "--source_video", source, "--extract_mode", "shorts",
               "--clip_count", str(_count(clip_count)), "--target_duration", str(_length(length)),
               "--min_duration", str(max(8, round(_length(length) * 0.6))),
               "--smart_crop", "--tighten", "--layout", layout, "--skip-upload",
               "--session_dir", session, "--output_json", results]
        cmd += web_args.filler_args(layout, filler_video)
        cmd += web_args.extras_args(clean_audio, hook_overlay, caption_emoji, bool(captions), broll=broll, auto_zoom=auto_zoom, cold_open=cold_open, stat_pops=stat_pops)
        cmd += web_args.edit_args(auto_edit, edit_strength)
        cmd += web_args.grade_args(grade)
        if captions:
            cmd += ["--use_remotion", "--caption_style", caption_style or "HORMOZI"]
            cmd += web_args.caption_look_args(caption_position, caption_size)
        cmd += web_args.game_args(game, game_mix, game_framing)
        cmd += web_args.template_args(visual_template, intro_animation, outro_animation, tpl_speaker, tpl_role, tpl_show, tpl_handle, tpl_headline, tpl_cta)
        if shape and shape != "9:16":
            cmd += ["--aspect_ratio", shape]
        cmd += web_args.llm_args(llm_provider)
        if (find or "").strip():
            cmd += ["--find", find.strip()]
        if (about or "").strip():
            cmd += ["--user_context", about.strip()]
        if visual:
            cmd += ["--visual_context"]
        if enhance:
            cmd += ["--enhance", "auto"]
        if (moments or "").strip():
            from engine.moments import parse_moments
            try:
                parse_moments(moments)                                   # a typo is reported here, before the long analysis
            except ValueError as e:
                raise gr.Error(f"Exact times: {e}")
            too_long = [t.strip() for t in re.split(r"[\n,;]+", moments) if t.strip() and _range_too_long(t)]
            if too_long:
                raise gr.Error(f"Exact times: '{too_long[0]}' is longer than a short (about a minute). To search a part of the video, use "
                               "'Only look between' instead: the tool then picks the best moments inside that range.")
            cmd += ["--moments", moments.strip()]
        if (between or "").strip():
            cmd += ["--only_between", between.strip()]
        for phrase in (cut or "").splitlines():
            if phrase.strip():
                cmd += ["--cut", phrase.strip()]
    cmd += lang_args
    if use_brand and not long_form:
        from shortsflow import brand
        if logo or (handle or "").strip() or (end_card or "").strip():
            save_brand(logo, handle, end_card, color, position)   # what is typed in the form counts, even if "Save" was not pressed
        cmd += brand.cli_args(ROOT)
    if reuse:
        keep = reuse_all in (True, "all")
        copied = _reuse.seed_session(os.path.dirname(reuse), session, keep_moments=keep)
        if copied:
            if keep and "--use_cache" not in cmd:
                cmd.append("--use_cache")
            print(f"[Log] Reusing {len(copied)} saved result(s) from the earlier run ({'transcript and all cache' if keep else 'transcript only'}).")
    plan_first = bool(plan_first) and not long_form
    if plan_first:
        cmd.append("--plan_only")
    save_command(session, cmd)
    stream = _stream_clip(cmd, results, long_form, minutes, find, plan_only=True) if plan_first else _stream_clip(cmd, results, long_form, minutes, find)
    yield from _with_drive(stream, drive)

def drive_upload_message(paths, folder):
    """Upload finished videos to a Google Drive folder; returns one plain-language line (never raises)."""
    from engine import drive_upload
    if not drive_upload.folder_id(folder):
        return "⚠️ Not uploaded: that is not a Google Drive folder link."
    try:
        done = drive_upload.upload([p for p in paths if p], folder)
    except Exception as e:
        return f"⚠️ Could not upload to Google Drive: {str(e)[:120]}"
    wanted = len(drive_upload.files_to_send(paths))
    if done and len(done) == wanted:
        return f"☁️ Uploaded {len(done)} video{'s' if len(done) != 1 else ''} to your Google Drive folder."
    return ("⚠️ Not uploaded to Google Drive (sign-in or access failed). One-time set-up: see the top of engine/drive_upload.py."
            if not done else f"⚠️ Uploaded {len(done)} of {wanted} videos to Google Drive.")


def _with_drive(stream, folder):
    """Pass a clip run's (status, log, cards) through; when it ends with cards and a Drive folder was given, upload them and say so."""
    last = None
    for last in stream:
        yield last
    if folder and (folder or "").strip() and last and last[2]:
        status, log, cards = last
        yield f"{status}\n\n☁️ Uploading to Google Drive...", log, cards
        yield f"{status}\n\n{drive_upload_message([c.get('video') for c in cards], folder)}", log, cards


def save_command(session, cmd):
    """Remember the exact command of a run, so it can be continued after a stop or a crash."""
    try:
        with open(os.path.join(session, "command.json"), "w", encoding="utf-8") as f:
            json.dump({"cmd": cmd}, f)
    except OSError:
        pass


def _stream_clip(cmd, results, long_form, minutes, find, plan_only=False):
    """Run the clipping pipeline and stream plain-language progress. Yields (status, log, cards)."""
    from shortsflow import onboarding, review
    progress, seen = onboarding.Progress(), 0
    status = progress.message
    yield status, "", []
    log, videos = "", []
    for log, videos in _run(cmd):
        lines = log.splitlines()
        for line in lines[seen:]:
            status = progress.feed(line)
        seen = len(lines)
        yield status, log, []
    if plan_only:
        from engine.plan import read_plan
        plan = read_plan(os.path.dirname(results))
        if plan and plan["moments"]:
            yield (f"📝 Found {len(plan['moments'])} moment(s). Nothing is rendered yet: check and adjust them in the **Review the moments** "
                   "section below, then press **Render these moments**."), log, []
        else:
            yield "❌ No moments were found. Open 'Technical details' below for the reason.", log, []
        return
    if long_form:
        cards = _cards_from_videos([v for v in videos if os.path.basename(v).startswith(("highlight_reel", "mashup"))] or videos[:1])
        for c in cards:
            c["title"] = "Highlights video"
        if cards:
            yield f"✅ Done! Your highlights video is ready below ({_minutes(minutes)} minutes or less).", log, cards
            return
        yield "❌ No highlights video was made. Open 'Technical details' below for the reason.", log, []
        return
    cards = review.load_results(results) or _cards_from_videos(videos)
    if not cards and (find or "").strip() and "No moments matching" in log:
        status = f"❌ Nothing in this video matched \"{find.strip()}\". Try other words, or clear that box to let the AI pick the best moments."
    elif not cards and not status.startswith("⚠️"):
        status = "❌ No shorts were made. Open 'Technical details' below for the reason, or check the setup list above."
    elif cards:
        status = f"✅ Done! {len(cards)} short{'s' if len(cards) != 1 else ''} ready: review them below."
    yield status, log, cards



def latest_plan(root):
    """The newest Start here session if it has a plan that was not rendered yet: {"session", "moments", "total"}, else None."""
    from engine.plan import read_plan
    from shortsflow import word_edit
    for d in sorted(glob.glob(os.path.join(root, "sessions", "web_*")), reverse=True)[:1]:
        plan = read_plan(d)
        if plan and not os.path.isfile(os.path.join(d, "results.json")):
            words = word_edit.load_words(d)
            ends = [m["end"] for m in plan["moments"]] + [w["end"] for w in words if w.get("end") is not None]
            source = plan.get("source_video") or ""
            for m in plan["moments"]:          # a small clip per moment, so it can be watched before rendering
                from engine.plan import make_preview
                m["preview"] = make_preview(source, m["start"], m["end"], os.path.join(d, "previews", f"m{m['index']}.mp4"))
            return {"session": d, "source": source, "moments": plan["moments"], "total": max(ends) if ends else 0.0}
    return None


def preview_handler(session, source, index):
    """Re-cut one moment's preview for the start and end currently in the boxes."""
    def run(start, end):
        from engine.plan import make_preview
        path = make_preview(source, start, end, os.path.join(session, "previews", f"m{index}_{int(float(start or 0))}_{int(float(end or 0))}.mp4"))
        if not path:
            raise gr.Error("Could not make a preview for those times.")
        return path
    return run


def load_plan():
    return latest_plan(ROOT)


def render_plan(session, *values):
    """Render the reviewed moments: values = keep flags, then starts, then ends (one per moment, in plan order)."""
    from engine.plan import read_plan, moments_text
    from engine.moments import parse_moments
    plan = read_plan(session)
    if not plan:
        raise gr.Error("That plan could not be read.")
    n = len(plan["moments"])
    keeps, starts, ends = values[:n], values[n:2 * n], values[2 * n:3 * n]
    extra = values[3 * n] if len(values) > 3 * n else ""
    chosen = [{"start": a, "end": b} for k, a, b in zip(keeps, starts, ends) if k and a is not None and b is not None]
    try:
        chosen += [{"start": m["start"], "end": m["end"]} for m in parse_moments(extra or "")]      # the user's own moments
    except ValueError as e:
        raise gr.Error(f"Your own moments: {e}")
    if not chosen:
        raise gr.Error("Keep at least one moment, or add your own.")
    text = moments_text(chosen)
    try:
        parse_moments(text)
    except ValueError as e:
        raise gr.Error(f"Moments: {e}")
    with open(os.path.join(session, "command.json"), encoding="utf-8") as f:
        cmd = list(json.load(f)["cmd"])
    while "--plan_only" in cmd:
        cmd.remove("--plan_only")
    if "--moments" in cmd:
        i = cmd.index("--moments")
        del cmd[i:i + 2]
    cmd += ["--moments", text]
    if "--use_cache" not in cmd:
        cmd.append("--use_cache")                 # the transcript from the analysis is reused
    save_command(session, cmd)
    yield from _stream_clip(cmd, os.path.join(session, "results.json"), False, 4, "")


def render_plan_handler(session):
    """A generator function (Gradio only streams progress from a real generator function, not from a lambda that returns one)."""
    def run(*values):
        yield from render_plan(session, *values)
    return run


def unfinished_runs(root):
    """[(label, command.json path)] of the Start here runs that never produced results (stopped, crashed, closed), newest first."""
    out = []
    for d in sorted(glob.glob(os.path.join(root, "sessions", "web_*")), reverse=True)[:30]:
        cmd_file = os.path.join(d, "command.json")
        if not os.path.isfile(cmd_file) or os.path.isfile(os.path.join(d, "results.json")) or os.path.isfile(os.path.join(d, "plan.json")):
            continue
        try:
            with open(cmd_file, "r", encoding="utf-8") as f:
                cmd = json.load(f)["cmd"]
            src = cmd[cmd.index("--source_video") + 1]
        except (OSError, ValueError, KeyError, IndexError):
            continue
        m = re.match(r"web_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})", os.path.basename(d))
        when = f"{m.group(3)}.{m.group(2)}.{m.group(1)} {m.group(4)}:{m.group(5)}" if m else os.path.basename(d)
        out.append((f"{when} - {os.path.basename(src.rstrip('/'))[:50]}", cmd_file))
    return out[:10]


def reusable_update(kind="clip"):
    return gr.update(choices=_reuse_choices(kind))


def _reuse_choices(kind):
    from shortsflow import reuse
    return reuse.earlier_runs(ROOT, kind)


def unfinished_update():
    return gr.update(choices=unfinished_runs(ROOT))


def continue_run(choice):
    """Continue an unfinished run in its own folder: the same command with --use_cache, so the transcript, the chosen moments and
    every segment that was already cut are reused instead of being redone."""
    if not choice:
        raise gr.Error("Pick an unfinished run first.")
    try:
        with open(choice, "r", encoding="utf-8") as f:
            cmd = list(json.load(f)["cmd"])
    except (OSError, ValueError, KeyError):
        raise gr.Error("That run's saved settings could not be read.")
    if "--use_cache" not in cmd:
        cmd.append("--use_cache")
    src = cmd[cmd.index("--source_video") + 1] if "--source_video" in cmd else ""
    if src and not src.startswith(("http://", "https://")) and not os.path.exists(src):
        raise gr.Error("The video file is no longer where it was, so this run cannot be continued. Start it again from Start here.")
    session = os.path.dirname(choice)
    long_form = "--extract_mode" in cmd and cmd[cmd.index("--extract_mode") + 1] == "long"
    minutes = 4
    if long_form and "--target_duration" in cmd:
        try:
            minutes = max(1, round(int(cmd[cmd.index("--target_duration") + 1]) / 60))
        except (ValueError, IndexError):
            pass
    find = cmd[cmd.index("--find") + 1] if "--find" in cmd and cmd.index("--find") + 1 < len(cmd) else ""
    yield from _stream_clip(cmd, os.path.join(session, "results.json"), long_form, minutes, find)

def open_earlier(choice):
    """Load an earlier run into the review screen."""
    from shortsflow import review
    cards = review.load_results(choice) if choice else []
    if not cards:
        raise gr.Error("That run has no shorts left (the files may have been moved or deleted).")
    return f"Opened an earlier run: {len(cards)} short(s).", cards


def earlier_runs():
    from shortsflow import review
    return gr.update(choices=[(name, path) for name, path in review.recent_runs(ROOT)])


def rerender_card(cards, index, style, start, end, cuts=None, caption_y=None):
    """Re-render one short (new caption style and/or start/end) with the run's cached analysis, then refresh its card.
    `cuts` = spans of the original video to remove (click-to-cut words); None leaves the short's cuts as they are."""
    from shortsflow import review
    card = next((c for c in cards or [] if c["index"] == index), None)
    if not card or not card.get("can_rerender"):
        raise gr.Error("This short cannot be edited (the data of its run is missing).")
    skip = getattr(gr, "skip", None)
    yield (skip() if skip else gr.update()), f"⏳ Re-rendering short {index}... this takes about a minute."
    cmd = [sys.executable, "-m", "engine.rerender", card["session_dir"], str(index)]
    if start is not None:
        cmd += ["--start", str(start)]
    if end is not None:
        cmd += ["--end", str(end)]
    if style and card.get("animated_captions"):
        cmd += ["--style", style]
    if cuts is not None:
        from shortsflow import word_edit
        cmd += ["--cuts", word_edit.spans_arg(cuts)]
    if caption_y is not None and card.get("animated_captions") and int(caption_y) != int(card.get("caption_y") or 1150):
        cmd += ["--caption_y", str(int(caption_y))]      # only when the slider was moved
    env =dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    if r.returncode != 0:
        reason = next((ln[len("[Error] "):] for ln in reversed((r.stdout or "").splitlines()) if ln.startswith("[Error] ")),
                      "The re-render failed. Open 'Technical details' or run the same steps again.")
        raise gr.Error(reason)
    fresh = next((c for c in review.load_results(card["results_path"]) if c["index"] == index), None)
    if fresh is None:
        raise gr.Error("The re-rendered short could not be loaded.")
    yield [fresh if c["index"] == index else c for c in cards], f"✅ Short {index} re-rendered."


def rerender_handler(index):
    """A real generator function for one card (a lambda that returns a generator is not treated as streaming by Gradio)."""
    def handler(cards, style, start, end, caption_y=None):
        yield from rerender_card(cards, index, style, start, end, caption_y=caption_y)
    return handler


def word_choices(card):
    """(choices, ticked, hint) for the click-to-cut word boxes of one short."""
    from shortsflow import word_edit
    words = word_edit.load_words(card["session_dir"])
    choices, ticked = word_edit.choices_for(words, card.get("start"), card.get("end"), card.get("cuts"))
    return choices, ticked, word_edit.summary(card.get("cuts") or [])


def cut_words_handler(index):
    """Re-render short `index` without the ticked words (an empty tick list brings every word back)."""
    def handler(cards, ticked, style, start, end, caption_y=None):
        from shortsflow import word_edit
        card = next((c for c in cards or [] if c["index"] == index), None)
        if not card:
            raise gr.Error("This short cannot be edited (the data of its run is missing).")
        words = word_edit.load_words(card["session_dir"])
        yield from rerender_card(cards, index, style, start, end, cuts=word_edit.spans_from_ticks(words, ticked), caption_y=caption_y)
    return handler


def tick_phrase_handler(index):
    """Tick every occurrence of a typed phrase among the words shown for short `index` (keeps the words already ticked)."""
    def handler(cards, phrase, ticked):
        from shortsflow import word_edit
        card = next((c for c in cards or [] if c["index"] == index), None)
        if not card:
            raise gr.Error("This short cannot be edited (the data of its run is missing).")
        words = word_edit.load_words(card["session_dir"])
        shown = [i for _label, i in word_edit.choices_for(words, card.get("start"), card.get("end"))[0]]
        hits = word_edit.phrase_ticks(words, shown, phrase)
        if not hits:
            return gr.update(), "That phrase is not in this short." if (phrase or "").strip() else "Type the words to find first."
        return gr.update(value=sorted(set(ticked or []) | set(hits))), "Ticked. Press 'Cut the ticked words' to remove them."
    return handler


def undo_handler(index):
    def handler(cards):
        return undo_card(cards, index)
    return handler


def undo_card(cards, index):
    from engine.rerender import undo_rerender
    from shortsflow import review
    card = next((c for c in cards or [] if c["index"] == index), None)
    if not card or not undo_rerender(card["session_dir"], index):
        raise gr.Error("There is no earlier version of this short to go back to.")
    fresh = next((c for c in review.load_results(card["results_path"]) if c["index"] == index), None)
    return [fresh if c["index"] == index else c for c in cards], f"↩ Short {index} is back to its earlier version."


def zip_cards(cards):
    from shortsflow import review
    if not cards:
        raise gr.Error("There are no shorts to download yet.")
    import time
    return gr.update(value=review.build_zip(cards, os.path.join(ROOT, "sessions", time.strftime("shorts_%Y%m%d_%H%M%S.zip"))), visible=True)


def _ai_provider_dropdown():
    """The same "AI text provider" choice on every tab that writes or translates text with an AI model."""
    return gr.Dropdown(web_args.AI_PROVIDER_CHOICES, value="auto", label="AI text provider",
                       info="Who writes the titles and translations. Automatic is fine; pick Local to keep the text on this PC (needs Ollama running).")


def _render_settings(with_aspect=True):
    with gr.Accordion("Render settings", open=False):
        with gr.Row():
            caption_style = gr.Dropdown(CAPTION_STYLES, value="HORMOZI", label="Caption style")
            # The choice is offered where it changes the result (clips can be 9:16, 1:1, 4:5 or 16:9).
            aspect_ratio = gr.Dropdown(ASPECTS, value="9:16", label="Aspect ratio") if with_aspect else gr.State("9:16")
        with gr.Row():
            llm_provider = gr.Dropdown(LLM_PROVIDERS, value="auto", label="LLM provider")
            tts_provider = gr.Dropdown(["auto", "edgetts", "elevenlabs", "voicestudio", "local"],
                                       value="auto", label="Voice (TTS) provider")
        use_remotion = gr.Checkbox(value=bool(shutil.which("node")), label="Remotion animated captions (needs Node.js)")   # off by default without Node: the render would fail
    return [caption_style, aspect_ratio, use_remotion, llm_provider, tts_provider]


# the word tick boxes of a long short are a long list: keep them in a box that scrolls
WORDS_CSS = """<style>
.sf-words { max-height: 230px; overflow-y: auto; }
.gradio-container { max-width: 980px !important; margin: 0 auto !important; padding: 0 20px !important; }
.sf-hero { padding: 28px 0 8px; }
.sf-hero h1 { font-size: 30px; font-weight: 700; letter-spacing: -0.02em; margin: 0 0 6px; }
.sf-hero p { margin: 0; font-size: 15px; opacity: .7; }
.sf-hero a { color: inherit; text-decoration: underline; }
.block-info, .gradio-container .info { font-size: 12.5px !important; opacity: .65; line-height: 1.45; }
.gradio-container label > span, .gradio-container .block-title { font-weight: 600; }
.gradio-container h3 { font-size: 18px; margin: 18px 0 6px; font-weight: 650; }
button.primary { height: 54px; font-size: 16px; font-weight: 650; border-radius: 12px; }
.gradio-container .form { border-radius: 14px; }
.gradio-container .accordion, .gradio-container details { border-radius: 14px; }
.sf-section { margin-top: 18px; }
</style>"""


MODE_KEYS = ["shorts", "clip", "dub", "recap", "reel", "idea"]


def web_args_modes():
    """[(label, key)] of the things you can make: the first screen of the app."""
    return [("Shorts or a highlights video", "shorts"), ("Dub into another language", "dub"), ("Recap (trip, wedding, event)", "recap"),
            ("Photo reel", "reel"), ("Video from an idea", "idea"), ("Clip tool (all options)", "clip")]


def build_ui():
    tolerate_missing_ffprobe()
    with gr.Blocks(title="ShortsFlow AI Studio", **_blocks_theme()) as demo:
        gr.HTML('<div class="sf-hero"><h1>ShortsFlow</h1><p>Turn a long video into shorts. It runs on this PC and nothing leaves it unless you switch on an '
                'online helper. <a href="https://github.com/ghost1412/shortsflow" target="_blank">GitHub</a></p></div>')
        gr.HTML(WORDS_CSS)
        from shortsflow.timeline import DRAG_JS
        demo.load(None, None, None, js=DRAG_JS)
        mode_card = gr.Radio(web_args_modes(), value="shorts", label="What do you want to make?",
                             info="Pick one. Only the steps for that appear below.")
        with gr.Column():
            with gr.Column(visible=True) as mode_col_shorts:
                gr.Markdown("### Your video\nPaste a link or upload a file. No account or API key is needed.")
                with gr.Row():
                    with gr.Column():
                        q_url = gr.Textbox(label="Video link (YouTube or other)", placeholder="https://www.youtube.com/watch?v=...")
                        q_upload = gr.File(label="...or upload a video from your computer", file_types=["video"], type="filepath")
                        q_sample = gr.Button("🎬 No video handy? Try a 2-minute sample", size="sm")
                        q_sample_note = gr.Markdown("")
                        q_mode = gr.Radio([("Short vertical clips (TikTok, Reels, Shorts)", "shorts"),
                                           ("One highlights video (long-form, landscape)", "long")],
                                          value="shorts", label="Format")
                        with gr.Row():
                            q_count = gr.Number(value=3, minimum=1, precision=0, label="How many shorts?",
                                                info="No limit. If the video does not have that many good moments you get fewer.")
                            q_length = gr.Slider(15, 60, value=30, step=5, label="Length of each short (seconds)",
                                                 info="The aim for each short. Clips end at the end of a sentence, so they can be a few seconds longer or shorter.")
                        q_minutes = gr.Number(value=4, minimum=1, precision=0, label="Highlights video length (minutes)", visible=False,
                                              info="No limit, but never longer than your video. Long reels take longer to make and the file gets big (about 2 GB for 15 minutes).")
                        with gr.Row():
                            q_kind = gr.Dropdown(kind_choices_with_none(), value="", label="What kind of video is it? (optional)",
                                              info="Fills in the edit style, game mode, picture, template and captions in one go. You can change each one under Advanced.")
                            q_picture = gr.Dropdown([("Automatic", "auto"), ("Fill the screen (crop: the sides are cut off)", "crop"),
                                                  ("Whole picture on a blurred background (fit: keeps everything in view)", "fit")],
                                                 value="auto", label="Picture in the tall frame",
                                                 info="Fit and crop are only about the picture. Templates (like Film bars) and edit styles are separate and are under Advanced.")
                        q_kind_note = gr.Markdown("")
                        with gr.Accordion("Advanced: moments, languages, edit style, captions, extras, brand", open=False):
                            with gr.Accordion("Pick the moments (optional)", open=False):
                                q_find = gr.Textbox(label="Only make shorts about...", placeholder="where they talk about pricing",
                                                    info="Describe the part you want. Leave empty to let the AI pick the best moments.")
                                q_between = gr.Textbox(label="Only look between (optional)", placeholder="30:00-60:00", max_lines=1,
                                                       info="The tool still picks the moments, but only inside this part of the video, for example after the first 30 minutes. It listens to the whole video first, so it is not faster.")
                                q_moments = gr.Textbox(label="Or give exact times (one per line)", lines=3, placeholder="7:00-7:45",
                                                       info="Makes shorts from exactly these moments, like a cutscene you spotted. Use minutes:seconds, e.g. 7:00-7:45 or 1:01:40-1:02:30. Leave empty to let the AI choose.")
                                q_about = gr.Textbox(label="What is this video about? (optional)", lines=2, placeholder="God of War 3 story playthrough",
                                                    info="Helps the AI judge which moments matter, for example when the speaker chats while the story happens on screen.")
                                q_visual = gr.Checkbox(label="Look at the picture too (slower)", value=False,
                                                       info="A vision model looks at a few frames of each candidate so the story on screen counts, not only the words. With a Gemini key in .env it uses Gemini (small frames are sent to Google); otherwise it needs a local one in Ollama (ollama pull gemma3:12b) and nothing leaves your PC.")
                                q_cut = gr.Textbox(label="Cut these words or phrases out (one per line)", lines=3, placeholder="you know, so basically",
                                                   info="Every time it is said, that bit is removed from the short.")
                            with gr.Accordion("Languages (optional)", open=False):
                                q_spoken = gr.Dropdown(SPOKEN_CHOICES, value="auto", label="Language spoken in the video")
                                q_caption_lang = gr.Dropdown(CAPTION_LANG_CHOICES, value="", label="Captions in...",
                                                             info="Translates the captions with AI (a free Groq key or Ollama is needed). "
                                                                  "Chinese, Japanese and Korean fonts download once, the first time you use them.")
                            with gr.Accordion("Edit style and look", open=False):
                                q_edit = gr.Dropdown(web_args.EDIT_STYLE_CHOICES, value="none", label="Auto-edit style",
                                                     info="Edits like an editor: cuts pauses and ums, zooms, cutaways, a teaser opening, colour and sound effects, "
                                                          "chosen for this kind of video. Turns on animated captions.")
                                q_edit_strength = gr.Radio(web_args.EDIT_STRENGTH_CHOICES, value="medium", label="How much editing",
                                                           info="Subtle keeps it quiet; Hyped uses everything.")
                                q_look = template_controls(" For a highlights video the template shows at the start and end, and the covers on the first and last second.")
                                q_grade = gr.Dropdown(web_args.COLOR_GRADE_CHOICES, value="default", label="Colour filter",
                                                      info="A colour look for the whole short. Automatic uses the Auto-edit style's own look (Hype: vibrant action, "
                                                           "Vlog: cinematic warm); pick one here to override it.")
                            with gr.Accordion("Captions", open=False):
                                q_captions = gr.Checkbox(value=bool(shutil.which("node")), label="Add animated captions",
                                                         info="Needs Node.js (nodejs.org). Untick if it is not installed.")
                                q_style = gr.Dropdown(CAPTION_CHOICES, value="HORMOZI", label="Caption style",
                                                   info="Only used when animated captions are on.")
                                q_style_img = gr.Image(value=style_preview("HORMOZI"), show_label=False, interactive=False, height=300)
                            with gr.Accordion("Game footage and caption position (optional)", open=False):
                                q_game = gr.Checkbox(label="This is game footage", value=False,
                                                     info="Picks story moments (cutscenes, dialogue) AND action moments (fights, gameplay, even with nobody talking), and keeps the whole screen in frame so the minimap and the game's own subtitles are not cut off.")
                                q_game_mix = gr.Dropdown(web_args.GAME_MIX_CHOICES, value="0.5", label="Story or action",
                                                         info="How many of the shorts are story moments and how many are action. Only used for game footage.")
                                q_game_frame = gr.Dropdown(web_args.GAME_FRAMING_CHOICES, value="auto", label="Framing for game footage",
                                                           info="Automatic looks at frames of the chosen moments: a HUD or subtitles at the sides keep the whole picture over blurred bars, a clean picture gets a full-screen portrait crop.")
                                with gr.Row():
                                    q_cap_pos = gr.Dropdown(web_args.CAPTION_POSITION_CHOICES, value="default", label="Caption position",
                                                            info="Where the animated captions sit. Normal height is the default.")
                                    q_cap_size = gr.Dropdown(web_args.CAPTION_SIZE_CHOICES, value="default", label="Caption size",
                                                             info="Size of the animated captions.")
                            with gr.Accordion("Extras (optional)", open=False):
                                q_clean = gr.Checkbox(label="Clean up the sound", info="Removes background noise and evens out the volume.")
                                q_enhance = gr.Checkbox(label="Auto-enhance the picture", info="Like an editor: each short is measured and a dark clip is lifted, a colour cast reduced, a dull one given a little colour, plus light sharpening. Only what is off is corrected. On your PC; it cannot add detail that is not there.")
                                q_hook = gr.Checkbox(label="Big title at the start", info="Shows the short's hook as a title for the first 3 seconds. Needs animated captions.")
                                q_emoji = gr.Checkbox(label="Emoji next to key words in the captions", info="Needs animated captions.")
                                q_filler = gr.Checkbox(label="Satisfying video underneath", info="Your clip on top, looping gameplay or satisfying footage below (shorts only). Without a file below, a video from assets/backgrounds/local or a free stock clip is used.")
                                q_filler_file = gr.File(label="Footage for the bottom half (optional)", file_types=["video"], type="filepath")
                                q_broll = gr.Checkbox(label="Stock cutaways on key words (B-roll)", info="A short stock clip over the upper part of the picture when a thing like \"money\" or \"car\" is said. Needs a free Pexels key (PEXELS_API_KEY) or clips in assets/backgrounds/local; otherwise nothing is added.")
                                q_zoom = gr.Checkbox(label="Zoom in on key moments", info="A subtle punch-in on numbers and strong words. Needs animated captions; skipped with the satisfying-video layout.")
                                q_cold = gr.Checkbox(label="Start with the best line (cold open)", info="The strongest sentence of each clip plays first as a 2-6 second teaser, then the clip starts from the beginning.")
                                q_stats = gr.Checkbox(label="Show numbers big (pop-ups)", info="When a striking number like $200 or 73% is said, it appears big on screen. Needs animated captions.")
                            with gr.Accordion("Your brand: logo, @handle, end card", open=False):
                                q_brand_on = gr.Checkbox(value=True, label="Add my brand to the shorts")
                                q_logo = gr.Image(label="Logo (PNG with a transparent background works best)", type="filepath",
                                                  height=140, sources=["upload"])
                                with gr.Row():
                                    q_handle = gr.Textbox(label="@handle", placeholder="@mychannel")
                                    q_color = gr.ColorPicker(label="Accent colour", value="#FFEA00")
                                with gr.Row():
                                    q_endcard = gr.Textbox(label="End card text (last 2 seconds)", placeholder="Follow for more")
                                    q_pos = gr.Dropdown(BRAND_POSITIONS, value="top-right", label="Logo position")
                                q_brand_msg = gr.Markdown("No brand saved yet.")
                                with gr.Row():
                                    q_brand_save = gr.Button("Save my brand", variant="secondary")
                                    q_brand_clear = gr.Button("Remove brand")
                            with gr.Accordion("Save these settings as my template", open=False):
                                gr.Markdown("Keeps the Auto-edit style, caption style, extras, colour grade, visual template and covers chosen above under a name, "
                                            "so you can pick them again in one step (or use them on the command line).")
                                q_tpl_name = gr.Textbox(label="Template name", placeholder="my-channel", max_lines=1)
                                q_tpl_save = gr.Button("Save as a template", variant="secondary")
                                q_tpl_msg = gr.Markdown("")
                        q_plan_first = gr.Checkbox(label="Let me review the moments first", value=False,
                                                   info="Finds the moments, then stops: you see each one on a timeline, adjust start and end or drop it, and only then it is rendered. Short clips only.")
                        q_btn = gr.Button("✨ Make my shorts", variant="primary")
                        q_stop = gr.Button("⏹ Stop", variant="stop")
                        q_status = gr.Markdown("Waiting for a video...")
                q_cards = gr.State([])
                q_plan = gr.State(None)

                @gr.render(inputs=q_plan)
                def show_plan(plan):
                    """Before rendering: every chosen moment with a timeline, start/end boxes and a keep box."""
                    if not plan or not plan.get("moments"):
                        return
                    from shortsflow import timeline as _tl
                    gr.Markdown("### Review the moments\nNothing is rendered yet. Adjust the start and end, untick a moment to drop it, then render.")
                    moms = plan["moments"]
                    total = plan.get("total") or 0.0
                    keeps, t0s, t1s = [], [], []
                    for m in moms:
                        others = [(o["start"], o["end"]) for o in moms if o["index"] != m["index"]]
                        with gr.Group():
                            score = f" · {int(m['score'])}/100" if isinstance(m.get("score"), (int, float)) else ""
                            keep = gr.Checkbox(value=True, label=f"{m['title']}{score}", interactive=True)
                            if m.get("reason"):
                                gr.Markdown(f"_{m['reason']}_")
                            vid = gr.Video(value=m.get("preview"), height=260, interactive=False, show_label=False,
                                           label="Preview of this moment (small copy; the render is full quality)")
                            with gr.Row():
                                t0 = gr.Number(value=m["start"], label="Start (seconds in the original video)", precision=1, minimum=0, interactive=True)
                                t1 = gr.Number(value=m["end"], label="End (seconds)", precision=1, minimum=0, interactive=True)
                            refresh = gr.Button("▶ Update the preview for these times", size="sm")
                            refresh.click(preview_handler(plan["session"], plan.get("source"), m["index"]), [t0, t1], vid)
                            strip = _tl.timeline_html(m["start"], m["end"], None, total, others)
                            if strip:
                                box = gr.HTML(strip)
                                with gr.Row():
                                    for lbl, d, is_start in (("Start -1 s", -1, True), ("Start +1 s", 1, True), ("End -1 s", -1, False), ("End +1 s", 1, False)):
                                        b = gr.Button(lbl, size="sm")
                                        b.click(lambda a, e, d=d, st=is_start, t=total, ot=others: _tl.nudge_view(a, e, d, st, t, None, ot),
                                                [t0, t1], [t0, t1, box])
                                for inp in (t0, t1):
                                    inp.change(lambda a, e, t=total, ot=others: _tl.timeline_html(a, e, None, t, ot) or gr.update(), [t0, t1], box)
                        keeps.append(keep)
                        t0s.append(t0)
                        t1s.append(t1)
                    own = gr.Textbox(label="Add your own moments (optional, one per line)", lines=2, placeholder="7:00-7:45",
                                     info="Rendered together with the ones kept above. Minutes:seconds, e.g. 7:00-7:45 or 1:01:40-1:02:30.")
                    go_plan = gr.Button("🎬 Render these moments", variant="primary")
                    go_plan.click(render_plan_handler(plan["session"]), [*keeps, *t0s, *t1s, own], [q_status, q_log, q_cards]
                                  ).then(lambda: None, None, q_plan)

                @gr.render(inputs=q_cards)
                def show_review(cards):
                    """One card per short: preview, score, copy-ready title/description/tags, and a remove button."""
                    from shortsflow import review
                    if not cards:
                        return
                    gr.Markdown("### Your shorts")
                    for c in cards:
                        with gr.Row(equal_height=False):
                            try:
                                gr.Video(value=c["video"], height=420, interactive=False, show_label=False, scale=1, min_width=240)
                            except Exception:   # no preview (unusual video setup): offer the file instead of breaking the page
                                gr.File(value=c["video"], label="Download this short", interactive=False, scale=1, min_width=240)
                            with gr.Column(scale=2):
                                score = f"{c['label'].title()} ({int(c['score'])}/100)" if c.get("score") is not None else "Not rated"
                                dur = f" · {c['duration']:.0f}s" if c.get("duration") else ""
                                gr.Markdown(f"### {c['title']}\n**{score}**{dur}" + (f"  \n_{c['reason']}_" if c.get("reason") else "")
                                            + (f"  \n🎬 Edited: {c['edit_summary']}" if c.get("edit_summary") else "")
                                            + ("  \n⚠️ Fallback pick: the analysis failed, so this is a fixed window, not a chosen moment." if c.get("fallback") else ""))
                                gr.Textbox(value=review.card_text(c), lines=6, interactive=False, show_label=False,
                                           placeholder="No title or description was written (it needs an AI key or Ollama).")
                                if c.get("title_variants"):
                                    with gr.Accordion("Other title ideas", open=False):
                                        gr.Textbox(value=review.variants_text(c), lines=3, interactive=False, show_label=False)
                                with gr.Row():
                                    up = gr.Button("👍 Good pick", size="sm")
                                    down = gr.Button("👎 Not good", size="sm")
                                    fb = gr.Markdown("")
                                up.click(lambda c=c: rate_clip(c, True), None, fb)
                                down.click(lambda c=c: rate_clip(c, False), None, fb)
                                rm = gr.Button("Remove this short", size="sm")
                                rm.click(lambda cs, i=c["index"]: [x for x in cs if x["index"] != i], q_cards, q_cards)
                                if c.get("can_rerender"):
                                    with gr.Accordion("Edit this short: style, start and end", open=False):
                                        if c.get("animated_captions"):
                                            st = gr.Dropdown(CAPTION_CHOICES, value=c.get("caption_style") or "HORMOZI", label="Caption style", interactive=True)
                                        else:
                                            st = gr.State(None)
                                            gr.Markdown("_Caption styles apply when animated captions are on. You can still change the start and end._")
                                        with gr.Row():
                                            t0 = gr.Number(value=c.get("start"), label="Start (seconds in the original video)", precision=1, minimum=0, interactive=True)
                                            t1 = gr.Number(value=c.get("end"), label="End (seconds)", precision=1, minimum=0, interactive=True)
                                        from shortsflow import timeline as _tl, word_edit as _we
                                        _words = _we.load_words(c["session_dir"])
                                        _total = _tl.source_length(_words, cards)
                                        _others = [(o.get("start"), o.get("end")) for o in cards if o["index"] != c["index"]]
                                        _strip = _tl.timeline_html(c.get("start"), c.get("end"), c.get("cuts"), _total, _others)
                                        if _strip:
                                            _strip_box = gr.HTML(_strip)
                                            with gr.Row():
                                                for _lbl, _d, _is_start in (("Start -1 s", -1, True), ("Start +1 s", 1, True),
                                                                            ("End -1 s", -1, False), ("End +1 s", 1, False)):
                                                    _b = gr.Button(_lbl, size="sm")
                                                    _b.click(lambda a, b, d=_d, s=_is_start, t=_total, cu=c.get("cuts"), ot=_others:
                                                             _tl.nudge_view(a, b, d, s, t, cu, ot),
                                                             [t0, t1], [t0, t1, _strip_box])
                                            for _box in (t0, t1):     # typed values redraw the strip too
                                                _box.change(lambda a, b, t=_total, cu=c.get("cuts"), ot=_others:
                                                            _tl.timeline_html(a, b, cu, t, ot) or gr.update(), [t0, t1], _strip_box)
                                        if c.get("animated_captions"):
                                            cy = gr.Slider(300, 1700, value=c.get("caption_y") or 1150, step=10,
                                                           label="Caption height (pixels from the top of the 1920 px tall short; lower number = higher up)",
                                                           interactive=True)
                                        else:
                                            cy = gr.State(None)
                                        with gr.Row():
                                            go = gr.Button("Re-render this short", size="sm", variant="secondary")
                                            back = gr.Button("Undo last change", size="sm")
                                        go.click(rerender_handler(c["index"]), [q_cards, st, t0, t1, cy], [q_cards, q_status])
                                        back.click(undo_handler(c["index"]), q_cards, [q_cards, q_status])
                                        choices, ticked, hint = word_choices(c)
                                        if choices:
                                            gr.Markdown(f"**Cut words out.** Tick the words you do not want, then press the button. {hint}")
                                            wd = gr.CheckboxGroup(choices, value=ticked, label="Words in this short", interactive=True,
                                                                  elem_classes=["sf-words"])
                                            with gr.Row():
                                                wfind = gr.Textbox(label="Or type a phrase to tick", placeholder="for example: you know what", scale=3)
                                                wfind_btn = gr.Button("Tick phrase", size="sm", scale=1)
                                            wgo = gr.Button("Cut the ticked words", size="sm", variant="secondary")
                                            wfind_btn.click(tick_phrase_handler(c["index"]), [q_cards, wfind, wd], [wd, q_status])
                                            wgo.click(cut_words_handler(c["index"]), [q_cards, wd, st, t0, t1, cy], [q_cards, q_status])

                with gr.Row():
                    q_zip_btn = gr.Button("⬇ Download all as .zip")
                    q_zip = gr.File(label="Your download", interactive=False, visible=False)
                with gr.Accordion("Tools and settings: earlier runs, Google Drive, setup check, AI key, technical log", open=False):
                    with gr.Accordion("Earlier runs: open, continue or reuse", open=False):
                        with gr.Tabs():
                            with gr.Tab("Open a finished run"):
                                q_runs = gr.Dropdown(label="Earlier runs", choices=[], interactive=True)
                                q_open = gr.Button("Open")
                            with gr.Tab("Continue one that stopped"):
                                gr.Markdown("A run that was stopped, closed or crashed carries on where it stopped: the analysis and the pieces "
                                            "already cut are reused.")
                                q_unfinished = gr.Dropdown(label="Unfinished runs", choices=[], interactive=True)
                                q_continue = gr.Button("Continue")
                            with gr.Tab("Run again, reusing its work"):
                                gr.Markdown("Pick an earlier run, change any setting above (captions, brand, extras...) and press the start button. "
                                            "The slow steps are skipped, so only the final rendering is done again, and you do not have to add the video again.")
                                q_reuse = gr.Dropdown(label="Earlier run to reuse", choices=[], interactive=True, value=None)
                                q_reuse_all = gr.Radio([("Skip transcription only (pick the moments again)", "transcript"),
                                                        ("Skip everything already done (transcript, moments, cut pieces)", "all")],
                                                       value="all", label="What to skip",
                                                       info="Choose \"Skip transcription only\" when you change the clip count, length or layout.")
                    with gr.Accordion("Upload the finished videos to Google Drive (optional)", open=False):
                        gr.Markdown("Paste a Drive folder link; the finished videos are uploaded when the run is done. The first time you sign in with Google "
                                    "(one-time set-up: see the top of `engine/drive_upload.py`). Nothing is uploaded unless you fill this in.")
                        q_drive = gr.Textbox(label="Google Drive folder link", placeholder="https://drive.google.com/drive/folders/...")
                    with gr.Accordion("Is my computer ready?", open=False):
                        q_check = gr.Markdown(setup_status())
                        gr.Button("Check again").click(setup_status, None, q_check)
                    with gr.Accordion("Want AI-written titles and descriptions? (optional, free)", open=False):
                        gr.Markdown("Pick any AI provider you have a key for. You can skip this; your shorts are made either way "
                                    "(with Ollama running on this PC no key is needed). The key is saved in your local `.env` file.")
                        q_llm = _ai_provider_dropdown()
                        q_key_provider = gr.Dropdown(web_args.LLM_KEY_CHOICES, value="groq", label="Provider")
                        q_key_help = gr.Markdown(web_args.llm_key_help("groq"))
                        q_key = gr.Textbox(label="API key", type="password")
                        q_key_msg = gr.Markdown()
                        q_key_provider.change(web_args.llm_key_help, q_key_provider, q_key_help)
                        gr.Button("Save key").click(save_llm_key, [q_key_provider, q_key], q_key_msg)
                    with gr.Accordion("Technical details", open=False):
                        q_log = gr.Textbox(label="Full log", lines=14, max_lines=14, autoscroll=True)
                q_style.change(style_preview, q_style, q_style_img)
                q_kind.change(apply_kind, q_kind, [q_edit, q_game, q_picture, q_look[0], q_style, q_kind_note])
                q_mode.change(lambda m: (gr.update(visible=m == "shorts"), gr.update(visible=m == "shorts"), gr.update(visible=m == "long")),
                              q_mode, [q_count, q_length, q_minutes])
                brand_form = [q_handle, q_endcard, q_color, q_pos, q_logo, q_brand_msg]
                q_brand_save.click(save_brand, [q_logo, q_handle, q_endcard, q_color, q_pos], q_brand_msg)
                q_brand_clear.click(clear_brand, None, brand_form)
                demo.load(brand_fields, None, brand_form)
                from shortsflow import sample as _sample
                q_sample.click(_sample.use_sample, None, [q_url, q_upload, q_sample_note])
                def _save_template(name, edit, style, clean, hook, emoji, broll, zoom, cold, stats, grade, tpl, intro, outro):
                    ok, msg = web_args.save_look_template(name, edit, style, clean, hook, emoji, broll, zoom, cold, stats, grade, tpl, intro, outro)
                    if not ok:
                        return msg, gr.update()
                    new = (name or "").strip().lower().replace(" ", "-")
                    return msg, gr.update(choices=web_args.edit_style_choices(), value=new if new else edit)
                q_tpl_save.click(_save_template, [q_tpl_name, q_edit, q_style, q_clean, q_hook, q_emoji, q_broll, q_zoom, q_cold, q_stats, q_grade,
                                                  q_look[0], q_look[1], q_look[2]], [q_tpl_msg, q_edit])
                q_run = q_btn.click(quick_clip, [q_url, q_upload, q_count, q_captions, q_style, q_brand_on, q_logo, q_handle, q_endcard, q_color, q_pos, q_mode, q_minutes, q_find, q_cut, q_spoken, q_caption_lang,
                             q_clean, q_hook, q_emoji, q_filler, q_filler_file, q_broll, q_zoom, q_cold, q_edit, q_edit_strength, q_stats, q_length, q_moments, q_about, q_visual, q_reuse, q_reuse_all, q_drive, q_enhance, q_grade,
                             q_game, q_game_mix, q_cap_pos, q_cap_size, q_game_frame, q_llm, *q_look, q_plan_first, q_between, q_picture],
                            [q_status, q_log, q_cards]).then(load_plan, None, q_plan)
                q_cont_run = q_continue.click(continue_run, q_unfinished, [q_status, q_log, q_cards])
                q_stop.click(stop_jobs, None, q_status, cancels=[q_run, q_cont_run]).then(unfinished_update, None, q_unfinished)
                demo.load(unfinished_update, None, q_unfinished)
                demo.load(lambda: reusable_update('clip'), None, q_reuse)
                q_zip_btn.click(zip_cards, q_cards, q_zip)
                q_open.click(open_earlier, q_runs, [q_status, q_cards])
                demo.load(earlier_runs, None, q_runs)

            with gr.Column(visible=False) as mode_col_clip:
                with gr.Row():
                    with gr.Column():
                        url = gr.Textbox(label="YouTube / video URL", placeholder="https://www.youtube.com/watch?v=...")
                        upload = gr.File(label="...or upload a video", file_types=["video"], type="filepath")
                        with gr.Row():
                            clip_count = gr.Number(value=3, minimum=1, precision=0, label="Number of clips", info="No limit.")
                            target_duration = gr.Slider(15, 60, value=30, step=5, label="Target length (s)", info="Shorts are never longer than 60 seconds.")
                        layout = gr.Radio(["single", "auto", "active", "split", "split_filler", "fit"], value="single", label="Framing",
                                          info="split_filler = clip on top, looping satisfying/gameplay footage below (your own videos in assets/backgrounds/local, else Pexels); auto = picks per clip (two-person shot -> cut to whoever talks; no face on screen, as in slides or a screen recording -> the whole picture over a blurred copy; otherwise a tracked crop); active = always cut to the speaker")
                        with gr.Row():
                            smart_crop = gr.Checkbox(value=True, label="Face-tracking 9:16 crop")
                            tighten = gr.Checkbox(value=True, label="Remove silences")
                            broll = gr.Checkbox(label="Auto B-roll")
                            srt = gr.Checkbox(label="Export .srt")
                        clip_settings = _render_settings(with_aspect=True)
                        with gr.Accordion("Game footage and caption position (optional)", open=False):
                            clip_game = gr.Checkbox(label="This is game footage", value=False,
                                                    info="Picks story moments (cutscenes, dialogue) AND action moments (fights, gameplay), and keeps the whole screen in frame (Framing \"single\" becomes \"fit\").")
                            clip_game_mix = gr.Dropdown(web_args.GAME_MIX_CHOICES, value="0.5", label="Story or action")
                            clip_game_frame = gr.Dropdown(web_args.GAME_FRAMING_CHOICES, value="auto", label="Framing for game footage",
                                                          info="Automatic picks per video. Only used for game footage with Framing \"single\".")
                            with gr.Row():
                                clip_cap_pos = gr.Dropdown(web_args.CAPTION_POSITION_CHOICES, value="default", label="Caption position")
                                clip_cap_size = gr.Dropdown(web_args.CAPTION_SIZE_CHOICES, value="default", label="Caption size")
                        with gr.Accordion("Extras", open=False):
                            with gr.Row():
                                clip_clean = gr.Checkbox(label="Clean audio", info="Noise reduction + loudness to about -14 LUFS")
                                clip_hook = gr.Checkbox(label="Hook title overlay", info="Needs Remotion captions")
                                clip_emoji = gr.Checkbox(label="Caption emoji", info="Needs Remotion captions")
                                clip_zoom = gr.Checkbox(label="Auto zoom", info="Punch-in on key words; needs Remotion captions, skipped for split_filler")
                                clip_cold = gr.Checkbox(label="Cold open", info="Strongest line first as a short teaser, then the clip")
                                clip_stats = gr.Checkbox(label="Number pop-ups", info="Striking numbers shown big when said; needs Remotion captions")
                            clip_filler = gr.File(label="Footage for the bottom half (Framing = split_filler)", file_types=["video"], type="filepath")
                            clip_spoken = gr.Dropdown(SPOKEN_CHOICES, value="en", label="Language spoken in the video")
                            with gr.Row():
                                clip_edit = gr.Dropdown(web_args.EDIT_STYLE_CHOICES, value="none", label="Auto-edit style")
                                clip_edit_strength = gr.Radio(web_args.EDIT_STRENGTH_CHOICES, value="medium", label="How much editing")
                            clip_look = template_controls(with_shape=False)      # the Clip tab has the aspect ratio in its render settings
                        clip_btn = gr.Button("Find viral clips", variant="primary")
                        clip_stop = gr.Button("⏹ Stop", variant="stop")
                    with gr.Column():
                        clip_videos = gr.Files(label="Rendered clips")
                        clip_log = gr.Textbox(label="Log", lines=22, max_lines=22, autoscroll=True)
                clip_run = clip_btn.click(
                    clip_video,
                    [url, upload, clip_count, target_duration, layout, smart_crop, tighten, broll, srt, *clip_settings,
                     clip_clean, clip_hook, clip_emoji, clip_filler, clip_zoom, clip_cold,
                     clip_spoken, clip_edit, clip_edit_strength, clip_stats,
                     clip_game, clip_game_mix, clip_cap_pos, clip_cap_size, clip_game_frame, *clip_look],
                    [clip_log, clip_videos],
                )
                clip_stop.click(stop_jobs, None, clip_log, cancels=[clip_run])

            with gr.Column(visible=False) as mode_col_dub:
                gr.Markdown("### Re-voice a video in another language\n"
                            "Translates what is said and records it with a computer voice, over the original sound. "
                            "One voice for everyone, no lip-sync. Needs internet for the voice, and a free Groq key or Ollama for the translation.")
                with gr.Row():
                    with gr.Column():
                        d_url = gr.Textbox(label="Video link (YouTube or other)", placeholder="https://www.youtube.com/watch?v=...")
                        d_upload = gr.File(label="...or upload a video from your computer", file_types=["video"], type="filepath")
                        d_lang = gr.Dropdown(web_args.dub_languages(), value="es", label="Dub into")
                        d_spoken = gr.Dropdown(SPOKEN_CHOICES, value="auto", label="Language spoken in the video")
                        with gr.Row():
                            d_voice = gr.Dropdown(web_args.DUB_VOICE_CHOICES, value="auto", label="Voice")
                            d_tts = gr.Dropdown(web_args.DUB_PROVIDER_CHOICES, value="auto", label="Voice engine",
                                                info="Automatic uses Edge online; Kokoro runs on this PC but only speaks English.")
                        d_original = gr.Dropdown(web_args.DUB_ORIGINAL_CHOICES, value="music", label="The video's own sound",
                                                 info="The first choice separates the voice from the music (needs 'pip install demucs'; about a minute per minute of video on the CPU) and removes only the voice. Without it the original is kept faintly.")
                        d_burn = gr.Checkbox(label="Burn the translated subtitles into the video", info="Slower: the video is re-encoded. The .srt file is always made.")
                        with gr.Row():
                            d_tone = gr.Dropdown(web_args.DUB_TONE_CHOICES, value="faithful", label="Tone of the translation",
                                                 info="Faithful keeps the speaker's own tone. The others make the AI rewrite each line (funny, sarcastic...) and keep the meaning; it can change what is said, so check the saved .json before you publish.")
                            d_delivery = gr.Dropdown(web_args.DUB_DELIVERY_CHOICES, value="neutral", label="How the voice speaks",
                                                     info="Speed and pitch of the computer voice, not real emotions.")
                        d_llm = _ai_provider_dropdown()
                        with gr.Row():
                            d_cap_size = gr.Dropdown(web_args.DUB_CAPTION_SIZE_CHOICES, value="default", label="Subtitle size",
                                                     info="Only used when the subtitles are burned in.")
                            d_cap_pos = gr.Dropdown(web_args.DUB_CAPTION_POSITION_CHOICES, value="bottom", label="Subtitle position",
                                                    info="Pick Raised if the video already has its own subtitles at the bottom.")
                        d_resume = gr.Dropdown(label="Continue an earlier dub that stopped (optional)", choices=[], value=None, interactive=True,
                                               info="Pick it to finish where it stopped: the saved translation and finished voices are reused, so no AI text or voice service is called for them. The video, language and voice come from that run.")
                        d_btn = gr.Button("🌍 Dub my video", variant="primary")
                        d_stop = gr.Button("⏹ Stop", variant="stop")
                    with gr.Column():
                        d_status = gr.Markdown("Waiting for a video...")
                        d_video = gr.Video(label="Dubbed video", interactive=False)
                        d_srt = gr.File(label="Translated subtitles (.srt)", interactive=False)
                with gr.Accordion("Technical details", open=False):
                    d_log = gr.Textbox(label="Full log", lines=14, max_lines=14, autoscroll=True)
                d_run = d_btn.click(dub_video, [d_upload, d_url, d_lang, d_spoken, d_burn, d_tts, d_voice, d_original, d_resume, d_tone, d_delivery, d_llm, d_cap_size, d_cap_pos], [d_status, d_log, d_video, d_srt])
                d_stop.click(stop_jobs, None, d_status, cancels=[d_run])
                demo.load(lambda: gr.update(choices=web_args.unfinished_dubs(ROOT)), None, d_resume)

            with gr.Column(visible=False) as mode_col_recap:
                gr.Markdown("### Turn many videos into one recap\n"
                            "Pick what the videos are. It opens with a hook over fast glimpses of the best shots, then shows everything part by part "
                            "(day by day for a trip) with a title card for each, and writes a summary. Add the videos in the order you filmed them.")
                with gr.Row():
                    with gr.Column():
                        t_kind = gr.Dropdown(web_args.RECAP_KIND_CHOICES, value="trip", label="What kind of videos are these?",
                                             info="Changes the wording and the options below. Wedding, event and family recaps never look up places.")
                        t_files = gr.File(label="Your videos (in filming order)", file_count="multiple", file_types=["video"], type="filepath")
                        t_name = gr.Textbox(label="Trip name", placeholder="Northvale: Pinemere, Larkwater and Stonegate")
                        t_length = gr.Slider(30, web_args.MAX_RECAP_SECONDS, value=60, step=15, label="Recap length (seconds)",
                                             info="A trip: 60-120. A wedding or event film can be 10-30 minutes (600-1800). Longer recaps take longer to make.")
                        t_music = gr.File(label="Music (optional)", file_types=["audio"], type="filepath")
                        with gr.Accordion("More options: stops, note, style, editing, extras (all optional)", open=False):
                            t_stops = gr.Textbox(label="Stops (optional): one per line or comma separated, e.g. Pinemere Lake, Larkwater Lake", placeholder="Pinemere Lake, Larkwater Lake, Stonegate Canyon",
                                                 info="Use this for a one-day tour or to name the parts. Leave empty for a trip of several days: name the files or folders day1, day2...")
                            t_note = gr.Textbox(label="A note about the trip (optional)", lines=3, info="The AI only uses facts you write here and what it sees in the pictures.",
                                                placeholder="We booked a 17 hour tour from Northvale. We left at 5 am and went first to Pinemere Lake.")
                            t_hook = gr.Textbox(label="Opening line (optional)", placeholder="Woke up at 4 AM just for this view",
                                                info="Shown over the first glimpses. Empty: written from your note.")
                            t_lines = gr.Textbox(label="A line for each part (optional), one per line, in order", lines=3,
                                                 placeholder="Fry the almonds in ghee\nRoast the khoya until golden",
                                                 info="Shown under each part's title and on its shots (a recipe step, a stop's note).")
                            t_llm = _ai_provider_dropdown()
                            t_steps = gr.Textbox(label="Steps for a step-by-step video (optional)", lines=8,
                                                 placeholder="Title: Build a bird house\nHook: Done in one afternoon\nNeeds: 4 pine boards | 30 screws | wood glue\nEnd: Ready to hang!\n\n1. Cut the boards | Cut four 20 cm sides\n2. Drill the hole | 3 cm hole, 12 cm up\n3. Assemble | Glue, then 6 screws per side",
                                                 info="Fill this in for a how-to video (a recipe, DIY, workout, tutorial): it opens on the finished result and goes through the steps, each with a title and a caption. One numbered step per line as \"1. Title | caption\". Optional lines: Title, Hook, Needs (or Ingredients, Materials, Tools), End. Your videos are split into the steps in the order you filmed them, so add them in order.")
                            t_open_result = gr.Checkbox(value=False, label="Open with the result first",
                                                        info="The opening shots come from the LAST part (the finished dish, the summit) before the story starts.")
                            t_style = gr.Radio([("Hook and glimpses first, then the whole trip", "hype"), ("Start at the first stop", "plain")],
                                               value="hype", label="Style")
                            t_edit = gr.Dropdown(web_args.EDIT_STYLE_CHOICES, value="none", label="Auto-edit style (the director)",
                                                 info="Like on Start here: a slow push-in or pull-out on every shot, sound effects at the cuts and the style's own colour look. "
                                                      "Hype / gaming is the punchiest; Vlog is warm and gentle.")
                            t_edit_strength = gr.Radio(web_args.EDIT_STRENGTH_CHOICES, value="medium", label="How much editing",
                                                       info="Subtle keeps it quiet; Hyped uses everything.")
                            t_grade = gr.Dropdown(web_args.RECAP_GRADE_CHOICES, value="default", label="Colour filter",
                                                  info="Automatic gives the cinematic look when the footage suits it and none otherwise. Pick one to force a look, or None to leave the colours as filmed.")
                            t_trans = gr.Dropdown(web_args.TRANSITION_CHOICES, value="auto", label="Transitions between shots",
                                                  info="Instead of plain cuts: a fast zoom punch, a whip pan, a white flash, a glitch, or a mix. How long they last follows 'How much editing'.")
                            t_look_fx = gr.Dropdown(web_args.SUBJECT_LOOK_CHOICES, value="auto", visible=False, label="Subject cut-out look",
                                                    info="Only for 'Subject cut-out': a bright outline can build up round the person before the background changes. Auto is plain (no outline) for now; the outline looks are experimental.")
                            t_look_color = gr.Dropdown(web_args.SUBJECT_COLOR_CHOICES, value="auto", visible=False, label="Outline colour",
                                                       info="Auto is white. You can also type a colour like #ffcc00 in the CLI (--subject_color).")
                            t_subject_max = gr.Number(value=2, minimum=0, maximum=6, precision=0, label="Most subject cut-outs",
                                                      info="Only where one person is alone in the shot; the other cuts use the other transitions.")
                            t_clean = gr.Checkbox(value=False, label="Clean up the sound (noise, volume)",
                                                  info="Only matters when the clips' own sound is in the recap (no music, or 'keep the original sound' ticked).")
                            t_sample = gr.Dropdown(web_args.RECAP_SAMPLE_CHOICES, value="auto", label="How many of your videos to look at",
                                                   info="With hundreds of videos, looking at all of them means reading every file once. Sampling picks videos spread evenly over each folder.")
                            t_look = gr.Checkbox(value=False, label="Look at the pictures too (better captions, fixes sideways clips; slower)",
                                                 info="Uses Gemini if you have a key (small frames are sent to Google), otherwise a local vision model if installed. Off = nothing leaves your PC for this.")
                            t_enhance = gr.Checkbox(value=False, label="Auto-enhance the video (like an editor: brightness, colour, sharpness)",
                                                    info="Each video is measured and corrected only where needed: dark clips lifted, a colour cast reduced, dull clips given a little colour. Done on your PC; it cannot add detail that is not there.")
                            t_both = gr.Checkbox(value=False, label="Make a portrait AND a landscape version",
                                                 info="Portrait uses your vertical clips, landscape your wide clips, so nothing is cropped small.")
                            t_places = gr.Checkbox(value=True, label="Name the places from the videos' GPS",
                                                   info="Sends the rounded GPS position (about 100 m) to the free OpenStreetMap service and shows tourist-place names. Untick to keep it all on your PC.")
                            t_keep = gr.Checkbox(value=False, label="Keep the original sound under the music (vows, speeches, laughter)",
                                                 info="Off = the song alone carries the edit. Only matters when you add music.")
                            t_reuse = gr.Dropdown(label="Reuse an earlier recap (optional)", choices=[], interactive=True, value=None,
                                                  info="Picture descriptions and place names are reused, and its videos too if you add none above.")
                            t_drive = gr.Textbox(label="Upload to a Google Drive folder (optional)", placeholder="https://drive.google.com/drive/folders/...",
                                                 info="Needs a one-time Google sign-in; see the top of engine/drive_upload.py.")
                        t_btn = gr.Button("🧳 Make my recap", variant="primary")
                        t_stop = gr.Button("⏹ Stop", variant="stop")
                    with gr.Column():
                        t_status = gr.Markdown("Waiting for your videos...")
                        t_video = gr.Video(label="Your recap", interactive=False)
                        t_md = gr.File(label="Itinerary (.md) and all versions", file_count="multiple", interactive=False)
                with gr.Accordion("Technical details", open=False):
                    t_log = gr.Textbox(label="Full log", lines=14, max_lines=14, autoscroll=True)
                t_run = t_btn.click(trip_recap, [t_files, t_name, t_stops, t_note, t_hook, t_length, t_style, t_music, t_reuse, t_drive, t_look, t_both, t_places, t_enhance, t_kind, t_keep, t_grade, t_edit, t_edit_strength, t_clean, t_sample, t_trans, t_look_fx, t_look_color, t_subject_max, t_lines, t_open_result, t_llm, t_steps],
                                    [t_status, t_log, t_video, t_md])
                t_kind.change(recap_kind_changed, t_kind, [t_name, t_stops, t_note, t_places, t_keep])
                t_stop.click(stop_jobs, None, t_status, cancels=[t_run])
                demo.load(lambda: reusable_update('trip'), None, t_reuse)

            with gr.Column(visible=False) as mode_col_reel:
                from engine.photo_reel_types import type_labels
                gr.Markdown("### Make a reel from your photos\n"
                            "Pick a type: it chooses the order, how long each photo stays, the captions, the title and the look. "
                            "Blurry and duplicate photos are skipped. Works with no account or key.")
                with gr.Row():
                    with gr.Column():
                        p_files = gr.File(label="Your photos (3 or more)", file_count="multiple", file_types=["image"], type="filepath")
                        p_type = gr.Dropdown(type_labels(), value="memories", label="Reel type",
                                             info="Travel recap and Memories follow the photo dates; Countdown and Product follow the order you add them.")
                        p_name = gr.Textbox(label="Title or name (optional)", placeholder="Lisbon, Mia, the new bottle...")
                        p_texts = gr.Textbox(label="Your own words for the photos (optional)", lines=3,
                                             placeholder="One line per photo, in order. Leave empty for automatic captions.")
                        p_music = gr.File(label="Music (optional, otherwise a built-in track)", file_types=["audio"], type="filepath")
                        p_len = gr.Slider(10, 60, value=24, step=2, label="Length (seconds)")
                        p_btn = gr.Button("📸 Make my reel", variant="primary")
                        p_stop = gr.Button("⏹ Stop", variant="stop")
                    with gr.Column():
                        p_status = gr.Markdown("Waiting for photos...")
                        p_video = gr.Video(label="Your reel", interactive=False)
                with gr.Accordion("Technical details", open=False):
                    p_log = gr.Textbox(label="Full log", lines=14, max_lines=14, autoscroll=True)
                p_run = p_btn.click(photo_reel, [p_files, p_type, p_name, p_texts, p_music, p_len], [p_status, p_log, p_video])
                p_stop.click(stop_jobs, None, p_status, cancels=[p_run])

            with gr.Column(visible=False) as mode_col_idea:
                with gr.Row():
                    with gr.Column():
                        mode = gr.Dropdown(GENERATE_MODES, value="FACTS", label="Mode")
                        category = gr.Textbox(label="Topic / category", placeholder="space mysteries")
                        prompt = gr.Textbox(label="Prompt (optional)", lines=2,
                                            placeholder="Explain how black holes bend light")
                        script = gr.Textbox(label="Your own script (optional, skips the LLM)", lines=4)
                        with gr.Row():
                            vibe = gr.Dropdown(VIBES, value="suspense", label="Music vibe")
                            voice = gr.Textbox(label="Voice (optional)", placeholder="en-US-GuyNeural")
                        gen_settings = _render_settings()
                        gen_btn = gr.Button("Generate short", variant="primary")
                        gen_stop = gr.Button("⏹ Stop", variant="stop")
                    with gr.Column():
                        gen_videos = gr.Files(label="Rendered video")
                        gen_log = gr.Textbox(label="Log", lines=22, max_lines=22, autoscroll=True)
                gen_run = gen_btn.click(
                    generate_short,
                    [mode, category, prompt, script, vibe, voice, *gen_settings],
                    [gen_log, gen_videos],
                )
                gen_stop.click(stop_jobs, None, gen_log, cancels=[gen_run])

        gr.Markdown("API keys are read from `.env` (`GEMINI_API_KEY`, `PEXELS_API_KEY`, ...). "
                    "See `env.example`. Your video files stay on this PC. Only what you switch on goes out: transcript text to an AI text provider when a key is set, "
                    "small frames to Gemini for `--visual_context` when a key is set, text to the voice service in the dub and idea-to-video modes, "
                    "stock-footage search words to Pexels, place names looked up on OpenStreetMap in trip recaps (turn it off with `--recap_no_geocode`), and any upload you ask for.")
        mode_cols = [mode_col_shorts, mode_col_clip, mode_col_dub, mode_col_recap, mode_col_reel, mode_col_idea]
        mode_card.change(lambda m: [gr.update(visible=m == k) for k in MODE_KEYS], mode_card, mode_cols)
    return demo


def main(argv=None):
    parser = argparse.ArgumentParser(description="ShortsFlow AI Studio WebUI")
    parser.add_argument("--host", default=os.getenv("WEBUI_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("WEBUI_PORT", "7860")))
    parser.add_argument("--share", action="store_true", help="Create a public gradio.live link (to use the app from a phone on another network). Protected by a password.")
    parser.add_argument("--auth", metavar="USER:PASSWORD", help="Require a login. Generated automatically for --share or a non-local --host.")
    parser.add_argument("--open", action="store_true", help="Open the page in your browser once it is ready.")
    cli = parser.parse_args(argv)

    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(ROOT, ".env"))
    except ImportError:
        pass
    try:  # the pipeline starts `ffmpeg` by name; make the bundled one visible when the PC has none
        from shortsflow.ffmpeg_path import ensure_ffmpeg_on_path
        ensure_ffmpeg_on_path(ROOT)
    except Exception:
        pass

    creds = web_args.resolve_auth(cli.auth, cli.share, cli.host)
    if creds and not cli.auth:
        print(f"[Login] username: {creds[0]}   password: {creds[1]}   (new on every start; use --auth user:pass to choose your own)", flush=True)
    build_ui().queue(default_concurrency_limit=1).launch(
        server_name=cli.host, server_port=cli.port, share=cli.share, inbrowser=cli.open,
        **({"auth": creds} if creds else {}), **_launch_theme()
    )


if __name__ == "__main__":
    main()
