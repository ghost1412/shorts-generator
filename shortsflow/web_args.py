"""Command-line building blocks for the browser app (kept free of gradio so they can be tested anywhere)."""
import glob
import os

FALLBACK_DUB_LANGUAGES = {
    "es": "Spanish", "hi": "Hindi", "de": "German", "fr": "French", "ja": "Japanese", "pt": "Portuguese",
    "zh": "Chinese", "it": "Italian", "ru": "Russian", "ko": "Korean", "ar": "Arabic", "en": "English",
    "tr": "Turkish", "nl": "Dutch", "pl": "Polish", "uk": "Ukrainian", "id": "Indonesian",
}


def extras_args(clean_audio=False, hook_overlay=False, caption_emoji=False, use_remotion=True, broll=False, auto_zoom=False, cold_open=False, stat_pops=False):
    """Flags for the optional extras. The hook title, caption emoji and punch-in zoom are drawn by Remotion, so
    they are left out when animated captions are off (the pipeline would ignore them anyway)."""
    args = []
    if clean_audio:
        args.append("--clean_audio")
    if broll:
        args.append("--broll")
    if cold_open:
        args.append("--cold_open")
    if use_remotion:
        if hook_overlay:
            args.append("--hook_overlay")
        if caption_emoji:
            args.append("--caption_emoji")
        if auto_zoom:
            args.append("--auto_zoom")
        if stat_pops:
            args.append("--stat_pops")
    return args


EDIT_STYLE_CHOICES = [("No auto-edit (pick my own options)", "none"), ("Podcast / interview", "podcast"),
                      ("Hype / gaming / reaction", "hype"), ("Educational / explainer", "educational"), ("Vlog / lifestyle", "vlog")]
EDIT_STRENGTH_CHOICES = [("Subtle", "subtle"), ("Medium", "medium"), ("Hyped", "hyped")]


def edit_args(style, strength="medium"):
    """`--auto_edit STYLE --edit_strength S` (nothing when no style is chosen)."""
    if not style or style == "none":
        return []
    return ["--auto_edit", style, "--edit_strength", strength if strength in ("subtle", "medium", "hyped") else "medium"]


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


def resolve_auth(auth, share, host="127.0.0.1"):
    """(username, password) or None. A shared (public) link, or an app listening on the network, must never be open to anyone
    who finds the URL: it can process videos on this PC and the 'Save key' box writes to .env. So without --auth a
    password is generated (and printed once)."""
    if auth:
        user, sep, pw = auth.partition(":")
        if not sep or not user or not pw:
            raise SystemExit("--auth must look like username:password")
        return user, pw
    if share or host not in ("127.0.0.1", "localhost", "::1"):
        import secrets
        return "shortsflow", secrets.token_urlsafe(9)
    return None


def stage_photos(paths, folder):
    """Copy uploaded photos into `folder`, keeping the order they were given (the reel types that use the given order read file
    names). Returns the folder. Non-image files are ignored."""
    import shutil
    from engine.photo_reel_types import PHOTO_EXTS
    os.makedirs(folder, exist_ok=True)
    n = 0
    for p in paths or []:
        src = p if isinstance(p, str) else getattr(p, "name", "")
        if src and src.lower().endswith(PHOTO_EXTS) and os.path.isfile(src):
            n += 1
            shutil.copy2(src, os.path.join(folder, f"{n:03d}_{os.path.basename(src)}"))
    return folder


def photo_reel_args(photos_dir, reel_type, name="", texts="", music=None, duration=24, session_dir=None):
    """Command-line arguments for a typed photo reel."""
    args = ["--mode", "PHOTO_REEL", "--photos_dir", photos_dir, "--reel_type", reel_type, "--target_duration", str(int(duration)),
            "--skip_upload"]
    if session_dir:
        args += ["--session_dir", session_dir]
    if (name or "").strip():
        args += ["--prompt", name.strip()]
    from engine.photo_reel_types import parse_texts
    for line in parse_texts(texts):
        args += ["--reel_text", line]
    if music:
        args += ["--music", music]
    return args


def find_photo_reel(session_dir):
    path = os.path.join(session_dir, "photo_reel.mp4")
    return path if os.path.isfile(path) else None
