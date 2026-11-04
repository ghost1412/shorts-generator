#!/usr/bin/env python3
"""
ShortsFlow AI Studio - Browser WebUI (Gradio)
Runs locally, in Docker, on Google Colab or on Hugging Face Spaces.

    python webui.py               # http://localhost:7860
    python webui.py --share       # public gradio.live link (Colab)
"""

import argparse
import glob
import os
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


def _blocks_theme():
    """Gradio 5 takes the theme in gr.Blocks(); Gradio 6 moved it to launch()."""
    return {} if _gradio_major() >= 6 else {"theme": gr.themes.Soft()}


def _launch_theme():
    return {"theme": gr.themes.Soft()} if _gradio_major() >= 6 else {}


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
CAPTION_STYLES = ["HORMOZI", "GLOW_BOX", "BOUNCE", "MINIMAL", "AUTO", "RANDOM"]
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


def _run(cmd):
    """Run main.py, streaming its log; yields (log, videos) and finally the new videos."""
    before = _snapshot_videos()
    log = f"$ {' '.join(cmd)}\n\n"
    yield log, []

    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    proc = subprocess.Popen(
        cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", env=env,
    )
    for line in proc.stdout:
        log += line
        yield log[-20000:], []
    proc.wait()

    after = _snapshot_videos()
    new = sorted(
        (p for p, m in after.items() if p not in before or m > before[p]),
        key=lambda p: after[p],
    )
    status = "✅ Done" if proc.returncode == 0 else f"❌ main.py exited with code {proc.returncode}"
    log += f"\n{status} - {len(new)} video(s) rendered.\n"
    yield log[-20000:], new


def _common_args(caption_style, aspect_ratio, use_remotion, llm_provider, tts_provider):
    args = ["--caption_style", caption_style, "--aspect_ratio", aspect_ratio,
            "--llm_provider", llm_provider, "--tts_provider", tts_provider, "--skip-upload"]
    if use_remotion:
        args.append("--use_remotion")
    return args


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


def clip_video(url, upload, clip_count, target_duration, layout, smart_crop, tighten, broll, srt,
               caption_style, aspect_ratio, use_remotion, llm_provider, tts_provider,
               clean_audio=False, hook_overlay=False, caption_emoji=False, filler_video=None, auto_zoom=False):
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
    cmd += web_args.extras_args(clean_audio, hook_overlay, caption_emoji, use_remotion, auto_zoom)
    cmd += web_args.filler_args(layout, filler_video)
    yield from _run(cmd)


def dub_video(upload, url, target_lang, spoken="auto", burn_captions=False, tts_provider="auto"):
    """Dub tab: translate a video's speech and re-voice it. Yields (status, log, video, srt)."""
    import time
    from shortsflow import onboarding
    source = upload or (url or "").strip()
    if not source:
        raise gr.Error("Paste a video link or upload a video file first.")
    if not target_lang:
        raise gr.Error("Choose the language to dub into.")
    session = os.path.join(ROOT, "sessions", time.strftime("dub_%Y%m%d_%H%M%S"))
    os.makedirs(session, exist_ok=True)
    cmd = [*_pipeline_cmd(), *web_args.dub_args(source, target_lang, spoken, burn_captions, session)]
    if tts_provider and tts_provider != "auto":
        cmd += ["--tts_provider", tts_provider]
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


def save_groq_key(key):
    from shortsflow import onboarding
    if onboarding.save_env_key(os.path.join(ROOT, ".env"), "GROQ_API_KEY", key):
        return "✅ Saved. AI titles and descriptions will use your free Groq key from the next run."
    return "⚠️ That does not look like a key. Copy it again from console.groq.com (no spaces)."


def _cards_from_videos(videos):
    """Fallback cards when the run wrote no results.json: just the files, with generic titles."""
    return [{"index": i, "video": v, "thumbnail": None, "title": f"Short {i}", "description": "", "tags": [], "hook": "",
             "reason": "", "score": None, "label": "unrated", "start": None, "end": None, "duration": None}
            for i, v in enumerate(videos, start=1)]


CAPTION_CHOICES = [("Bold yellow (Hormozi)", "HORMOZI"), ("Pink glow box", "GLOW_BOX"),
                   ("Bouncy gold", "BOUNCE"), ("Clean dark boxes", "MINIMAL")]
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


def quick_clip(url, upload, clip_count, captions, caption_style="HORMOZI", use_brand=True,
               logo=None, handle="", end_card="", color=None, position="top-right", mode="shorts", minutes=4, find="", cut="", spoken="auto", caption_lang="",
               clean_audio=False, hook_overlay=False, caption_emoji=False, filler=False, filler_video=None, auto_zoom=False):
    """The beginner flow: a video in, shorts out, with plain-language progress instead of a raw log.
    Yields (status, log, cards): `cards` feeds the review screen."""
    import time
    from shortsflow import onboarding, review
    source = upload or (url or "").strip()
    if not source:
        raise gr.Error("Paste a video link or upload a video file first.")
    session = os.path.join(ROOT, "sessions", time.strftime("web_%Y%m%d_%H%M%S"))
    results = os.path.join(session, "results.json")
    os.makedirs(session, exist_ok=True)
    long_form = mode == "long"
    layout = "split_filler" if filler else "auto"
    lang_args = ["--language", (spoken or "auto")]
    if caption_lang:
        lang_args += ["--caption_lang", caption_lang]
    if long_form:   # one highlights video made of the best moments, in story order (landscape, like the source)
        cmd = [*_pipeline_cmd(), "--source_video", source, "--extract_mode", "long",
               "--target_duration", str(_minutes(minutes) * 60), "--skip-upload",
               "--session_dir", session, "--output_json", results]
        if captions:
            cmd += ["--reel_captions"]
    else:
        cmd = [*_pipeline_cmd(), "--source_video", source, "--extract_mode", "shorts",
               "--clip_count", str(_count(clip_count)), "--smart_crop", "--tighten", "--layout", layout, "--skip-upload",
               "--session_dir", session, "--output_json", results]
        cmd += web_args.filler_args(layout, filler_video)
        cmd += web_args.extras_args(clean_audio, hook_overlay, caption_emoji, bool(captions), auto_zoom)
        if captions:
            cmd += ["--use_remotion", "--caption_style", caption_style or "HORMOZI"]
        if (find or "").strip():
            cmd += ["--find", find.strip()]
        for phrase in (cut or "").splitlines():
            if phrase.strip():
                cmd += ["--cut", phrase.strip()]
    cmd += lang_args
    if use_brand and not long_form:
        from shortsflow import brand
        if logo or (handle or "").strip() or (end_card or "").strip():
            save_brand(logo, handle, end_card, color, position)   # what is typed in the form counts, even if "Save" was not pressed
        cmd += brand.cli_args(ROOT)
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


def rerender_card(cards, index, style, start, end, cuts=None):
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
    def handler(cards, style, start, end):
        yield from rerender_card(cards, index, style, start, end)
    return handler


def word_choices(card):
    """(choices, ticked, hint) for the click-to-cut word boxes of one short."""
    from shortsflow import word_edit
    words = word_edit.load_words(card["session_dir"])
    choices, ticked = word_edit.choices_for(words, card.get("start"), card.get("end"), card.get("cuts"))
    return choices, ticked, word_edit.summary(card.get("cuts") or [])


def cut_words_handler(index):
    """Re-render short `index` without the ticked words (an empty tick list brings every word back)."""
    def handler(cards, ticked, style, start, end):
        from shortsflow import word_edit
        card = next((c for c in cards or [] if c["index"] == index), None)
        if not card:
            raise gr.Error("This short cannot be edited (the data of its run is missing).")
        words = word_edit.load_words(card["session_dir"])
        yield from rerender_card(cards, index, style, start, end, cuts=word_edit.spans_from_ticks(words, ticked))
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


def _render_settings(with_aspect=True):
    with gr.Accordion("Render settings", open=False):
        with gr.Row():
            caption_style = gr.Dropdown(CAPTION_STYLES, value="HORMOZI", label="Caption style")
            # Clipping always produces 9:16, so the choice is only offered where it changes the result.
            aspect_ratio = gr.Dropdown(ASPECTS, value="9:16", label="Aspect ratio") if with_aspect else gr.State("9:16")
        with gr.Row():
            llm_provider = gr.Dropdown(LLM_PROVIDERS, value="auto", label="LLM provider")
            tts_provider = gr.Dropdown(["auto", "edgetts", "elevenlabs", "voicestudio", "local"],
                                       value="auto", label="Voice (TTS) provider")
        use_remotion = gr.Checkbox(value=True, label="Remotion animated captions (needs Node.js)")
    return [caption_style, aspect_ratio, use_remotion, llm_provider, tts_provider]


def build_ui():
    tolerate_missing_ffprobe()
    with gr.Blocks(title="ShortsFlow AI Studio", **_blocks_theme()) as demo:
        gr.Markdown(
            "# ⚡ ShortsFlow AI Studio\n"
            "Open-source, local-first Opus Clip alternative. "
            "[GitHub](https://github.com/ghost1412/shorts-generator) · ⭐ Star if it helps!"
        )
        with gr.Tabs():
            with gr.Tab("🚀 Start here"):
                gr.Markdown("### Make shorts from a video in one click\n"
                            "No account or API key is needed for this. Paste a link or upload a video, then press the button.")
                with gr.Row():
                    with gr.Column():
                        q_url = gr.Textbox(label="Video link (YouTube or other)", placeholder="https://www.youtube.com/watch?v=...")
                        q_upload = gr.File(label="...or upload a video from your computer", file_types=["video"], type="filepath")
                        q_mode = gr.Radio([("Short vertical clips (TikTok, Reels, Shorts)", "shorts"),
                                           ("One highlights video (long-form, landscape)", "long")],
                                          value="shorts", label="What do you want?")
                        q_count = gr.Number(value=3, minimum=1, precision=0, label="How many shorts?",
                                            info="No limit. If the video does not have that many good moments you get fewer.")
                        q_minutes = gr.Number(value=4, minimum=1, precision=0, label="Highlights video length (minutes)", visible=False,
                                              info="No limit, but never longer than your video. Long reels take longer to make and the file gets big (about 2 GB for 15 minutes).")
                        with gr.Accordion("Pick the moments (optional)", open=False):
                            q_find = gr.Textbox(label="Only make shorts about...", placeholder="where they talk about pricing",
                                                info="Describe the part you want. Leave empty to let the AI pick the best moments.")
                            q_cut = gr.Textbox(label="Cut these words or phrases out (one per line)", lines=3, placeholder="you know, so basically",
                                               info="Every time it is said, that bit is removed from the short.")
                        with gr.Accordion("Languages (optional)", open=False):
                            q_spoken = gr.Dropdown(SPOKEN_CHOICES, value="auto", label="Language spoken in the video")
                            q_caption_lang = gr.Dropdown(CAPTION_LANG_CHOICES, value="", label="Captions in...",
                                                         info="Translates the captions with AI (a free Groq key or Ollama is needed). "
                                                              "Chinese, Japanese and Korean fonts download once, the first time you use them.")
                        q_captions = gr.Checkbox(value=bool(shutil.which("node")), label="Add animated captions",
                                                 info="Needs Node.js (nodejs.org). Untick if it is not installed.")
                        q_style = gr.Radio(CAPTION_CHOICES, value="HORMOZI", label="Caption style",
                                           info="Only used when animated captions are on.")
                        q_style_img = gr.Image(value=style_preview("HORMOZI"), show_label=False, interactive=False, height=300)
                        with gr.Accordion("Extras (optional)", open=False):
                            q_clean = gr.Checkbox(label="Clean up the sound", info="Removes background noise and evens out the volume.")
                            q_hook = gr.Checkbox(label="Big title at the start", info="Shows the short's hook as a title for the first 3 seconds. Needs animated captions.")
                            q_emoji = gr.Checkbox(label="Emoji next to key words in the captions", info="Needs animated captions.")
                            q_filler = gr.Checkbox(label="Satisfying video underneath", info="Your clip on top, looping gameplay or satisfying footage below (shorts only). Without a file below, a video from assets/backgrounds/local or a free stock clip is used.")
                            q_filler_file = gr.File(label="Footage for the bottom half (optional)", file_types=["video"], type="filepath")
                            q_zoom = gr.Checkbox(label="Zoom in on key moments", info="A subtle punch-in on numbers and strong words. Needs animated captions; skipped with the satisfying-video layout.")
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
                        q_btn = gr.Button("✨ Make my shorts", variant="primary")
                    with gr.Column():
                        q_status = gr.Markdown("Waiting for a video...")
                q_cards = gr.State([])

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
                                gr.Markdown(f"### {c['title']}\n**{score}**{dur}" + (f"  \n_{c['reason']}_" if c.get("reason") else ""))
                                gr.Textbox(value=review.card_text(c), lines=6, interactive=False, show_label=False,
                                           placeholder="No title or description was written (it needs an AI key or Ollama).")
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
                                        with gr.Row():
                                            go = gr.Button("Re-render this short", size="sm", variant="secondary")
                                            back = gr.Button("Undo last change", size="sm")
                                        go.click(rerender_handler(c["index"]), [q_cards, st, t0, t1], [q_cards, q_status])
                                        back.click(undo_handler(c["index"]), q_cards, [q_cards, q_status])
                                        choices, ticked, hint = word_choices(c)
                                        if choices:
                                            gr.Markdown(f"**Cut words out.** Tick the words you do not want, then press the button. {hint}")
                                            wd = gr.CheckboxGroup(choices, value=ticked, label="Words in this short", interactive=True)
                                            wgo = gr.Button("Cut the ticked words", size="sm", variant="secondary")
                                            wgo.click(cut_words_handler(c["index"]), [q_cards, wd, st, t0, t1], [q_cards, q_status])

                with gr.Row():
                    q_zip_btn = gr.Button("⬇ Download all as .zip")
                    q_zip = gr.File(label="Your download", interactive=False, visible=False)
                with gr.Accordion("Open an earlier run", open=False):
                    q_runs = gr.Dropdown(label="Earlier runs", choices=[], interactive=True)
                    q_open = gr.Button("Open")
                with gr.Accordion("Is my computer ready?", open=False):
                    q_check = gr.Markdown(setup_status())
                    gr.Button("Check again").click(setup_status, None, q_check)
                with gr.Accordion("Want AI-written titles and descriptions? (optional, free)", open=False):
                    gr.Markdown("Get a free key at [console.groq.com](https://console.groq.com) (sign in, then *API Keys*), paste it here and save. "
                                "You can skip this; your shorts are made either way.")
                    q_key = gr.Textbox(label="Groq API key", type="password", placeholder="gsk_...")
                    q_key_msg = gr.Markdown()
                    gr.Button("Save key").click(save_groq_key, q_key, q_key_msg)
                with gr.Accordion("Technical details", open=False):
                    q_log = gr.Textbox(label="Full log", lines=14, max_lines=14, autoscroll=True)
                q_style.change(style_preview, q_style, q_style_img)
                q_mode.change(lambda m: (gr.update(visible=m == "shorts"), gr.update(visible=m == "long")), q_mode, [q_count, q_minutes])
                brand_form = [q_handle, q_endcard, q_color, q_pos, q_logo, q_brand_msg]
                q_brand_save.click(save_brand, [q_logo, q_handle, q_endcard, q_color, q_pos], q_brand_msg)
                q_brand_clear.click(clear_brand, None, brand_form)
                demo.load(brand_fields, None, brand_form)
                q_btn.click(quick_clip, [q_url, q_upload, q_count, q_captions, q_style, q_brand_on, q_logo, q_handle, q_endcard, q_color, q_pos, q_mode, q_minutes, q_find, q_cut, q_spoken, q_caption_lang,
                             q_clean, q_hook, q_emoji, q_filler, q_filler_file, q_zoom],
                            [q_status, q_log, q_cards])
                q_zip_btn.click(zip_cards, q_cards, q_zip)
                q_open.click(open_earlier, q_runs, [q_status, q_cards])
                demo.load(earlier_runs, None, q_runs)

            with gr.Tab("✂️ Clip (advanced)"):
                with gr.Row():
                    with gr.Column():
                        url = gr.Textbox(label="YouTube / video URL", placeholder="https://www.youtube.com/watch?v=...")
                        upload = gr.File(label="...or upload a video", file_types=["video"], type="filepath")
                        with gr.Row():
                            clip_count = gr.Number(value=3, minimum=1, precision=0, label="Number of clips", info="No limit.")
                            target_duration = gr.Slider(15, 90, value=30, step=5, label="Target length (s)")
                        layout = gr.Radio(["single", "auto", "active", "split", "split_filler"], value="single", label="Framing",
                                          info="split_filler = clip on top, looping satisfying/gameplay footage below (your own videos in assets/backgrounds/local, else Pexels); auto = picks per clip (two-person shot -> cut to whoever talks, otherwise a tracked crop); active = always cut to the speaker")
                        with gr.Row():
                            smart_crop = gr.Checkbox(value=True, label="Face-tracking 9:16 crop")
                            tighten = gr.Checkbox(value=True, label="Remove silences")
                            broll = gr.Checkbox(label="Auto B-roll")
                            srt = gr.Checkbox(label="Export .srt")
                        clip_settings = _render_settings(with_aspect=False)
                        with gr.Accordion("Extras", open=False):
                            with gr.Row():
                                clip_clean = gr.Checkbox(label="Clean audio", info="Noise reduction + loudness to about -14 LUFS")
                                clip_hook = gr.Checkbox(label="Hook title overlay", info="Needs Remotion captions")
                                clip_emoji = gr.Checkbox(label="Caption emoji", info="Needs Remotion captions")
                                clip_zoom = gr.Checkbox(label="Auto zoom", info="Punch-in on key words; needs Remotion captions, skipped for split_filler")
                            clip_filler = gr.File(label="Footage for the bottom half (Framing = split_filler)", file_types=["video"], type="filepath")
                        clip_btn = gr.Button("Find viral clips", variant="primary")
                    with gr.Column():
                        clip_videos = gr.Files(label="Rendered clips")
                        clip_log = gr.Textbox(label="Log", lines=22, max_lines=22, autoscroll=True)
                clip_btn.click(
                    clip_video,
                    [url, upload, clip_count, target_duration, layout, smart_crop, tighten, broll, srt, *clip_settings,
                     clip_clean, clip_hook, clip_emoji, clip_filler, clip_zoom],
                    [clip_log, clip_videos],
                )

            with gr.Tab("🌍 Dub a video"):
                gr.Markdown("### Re-voice a video in another language\n"
                            "Translates what is said and records it with a computer voice, over the original sound. "
                            "One voice for everyone, no lip-sync. Needs internet for the voice, and a free Groq key or Ollama for the translation.")
                with gr.Row():
                    with gr.Column():
                        d_url = gr.Textbox(label="Video link (YouTube or other)", placeholder="https://www.youtube.com/watch?v=...")
                        d_upload = gr.File(label="...or upload a video from your computer", file_types=["video"], type="filepath")
                        d_lang = gr.Dropdown(web_args.dub_languages(), value="es", label="Dub into")
                        d_spoken = gr.Dropdown(SPOKEN_CHOICES, value="auto", label="Language spoken in the video")
                        d_burn = gr.Checkbox(label="Burn the translated subtitles into the video", info="Slower: the video is re-encoded. The .srt file is always made.")
                        d_btn = gr.Button("🌍 Dub my video", variant="primary")
                    with gr.Column():
                        d_status = gr.Markdown("Waiting for a video...")
                        d_video = gr.Video(label="Dubbed video", interactive=False)
                        d_srt = gr.File(label="Translated subtitles (.srt)", interactive=False)
                with gr.Accordion("Technical details", open=False):
                    d_log = gr.Textbox(label="Full log", lines=14, max_lines=14, autoscroll=True)
                d_btn.click(dub_video, [d_upload, d_url, d_lang, d_spoken, d_burn], [d_status, d_log, d_video, d_srt])

            with gr.Tab("🪄 Generate from an idea"):
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
                    with gr.Column():
                        gen_videos = gr.Files(label="Rendered video")
                        gen_log = gr.Textbox(label="Log", lines=22, max_lines=22, autoscroll=True)
                gen_btn.click(
                    generate_short,
                    [mode, category, prompt, script, vibe, voice, *gen_settings],
                    [gen_log, gen_videos],
                )

        gr.Markdown("API keys are read from `.env` (`GEMINI_API_KEY`, `PEXELS_API_KEY`, ...). "
                    "See `env.example`. Nothing is uploaded unless you run `main.py` without `--skip-upload`.")
    return demo


def main(argv=None):
    parser = argparse.ArgumentParser(description="ShortsFlow AI Studio WebUI")
    parser.add_argument("--host", default=os.getenv("WEBUI_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("WEBUI_PORT", "7860")))
    parser.add_argument("--share", action="store_true", help="Create a public gradio.live link (useful on Colab).")
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

    build_ui().queue(default_concurrency_limit=1).launch(
        server_name=cli.host, server_port=cli.port, share=cli.share, inbrowser=cli.open, **_launch_theme()
    )


if __name__ == "__main__":
    main()
