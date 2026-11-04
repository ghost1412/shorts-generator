"""Command-line building blocks for the browser app (kept free of gradio so they can be tested anywhere)."""
import glob
import os

FALLBACK_DUB_LANGUAGES = {
    "es": "Spanish", "hi": "Hindi", "de": "German", "fr": "French", "ja": "Japanese", "pt": "Portuguese",
    "zh": "Chinese", "it": "Italian", "ru": "Russian", "ko": "Korean", "ar": "Arabic", "en": "English",
    "tr": "Turkish", "nl": "Dutch", "pl": "Polish", "uk": "Ukrainian", "id": "Indonesian",
}


def extras_args(clean_audio=False, hook_overlay=False, caption_emoji=False, use_remotion=True, broll=False, auto_zoom=False):
    """Flags for the optional extras. The hook title, caption emoji and punch-in zoom are drawn by Remotion, so
    they are left out when animated captions are off (the pipeline would ignore them anyway)."""
    args = []
    if clean_audio:
        args.append("--clean_audio")
    if broll:
        args.append("--broll")
    if use_remotion:
        if hook_overlay:
            args.append("--hook_overlay")
        if caption_emoji:
            args.append("--caption_emoji")
        if auto_zoom:
            args.append("--auto_zoom")
    return args


def filler_args(layout, filler_video=None):
    """`--filler_video` only matters for the split_filler layout; an empty choice lets the pipeline pick footage."""
    path = (filler_video or "").strip() if isinstance(filler_video, str) else ""
    if layout == "split_filler" and path:
        return ["--filler_video", path]
    return []


def dub_languages():
    """(name, code) pairs for the dubbing dropdown, from the engine when importable."""
    try:
        from engine.dubbing import LANG_NAMES, supported_languages
        return [(LANG_NAMES.get(code, code), code) for code in supported_languages()]
    except Exception:
        return [(name, code) for code, name in sorted(FALLBACK_DUB_LANGUAGES.items(), key=lambda kv: kv[1])]


DUB_VOICE_CHOICES = [("Automatic (female)", "auto"), ("Female", "female"), ("Male", "male")]
DUB_PROVIDER_CHOICES = [("Automatic", "auto"), ("Edge (online, many languages)", "edgetts"), ("Kokoro (on this PC, English only)", "kokoro")]


def dub_args(source, target_lang, spoken="auto", burn_captions=False, session_dir=None, tts_provider="auto", voice="auto"):
    """Arguments (after the pipeline command) for `--mode DUB`. 'auto' voice / provider leave the flags out."""
    args = ["--mode", "DUB", "--source_video", source, "--target_lang", target_lang,
            "--language", (spoken or "auto")]
    if burn_captions:
        args.append("--dub_captions")
    if voice in ("female", "male"):
        args += ["--dub_voice", voice]
    if tts_provider and tts_provider != "auto":
        args += ["--tts_provider", tts_provider]
    if session_dir:
        args += ["--session_dir", session_dir]
    return args


def find_dub_outputs(session_dir):
    """(dubbed video, translated .srt) written to a dubbing session folder; either is None when missing."""
    videos = sorted(glob.glob(os.path.join(session_dir, "*_dub_*.mp4")), key=os.path.getmtime)
    srts = sorted(glob.glob(os.path.join(session_dir, "*.srt")), key=os.path.getmtime)
    return (videos[-1] if videos else None, srts[-1] if srts else None)
