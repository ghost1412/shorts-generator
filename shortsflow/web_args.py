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
from engine import transitions as _transitions  # noqa: E402
TRANSITION_CHOICES = _transitions.LABELS
from engine import subject_cut as _subject_cut  # noqa: E402
SUBJECT_LOOK_CHOICES = _subject_cut.LOOK_LABELS
SUBJECT_COLOR_CHOICES = _subject_cut.COLOR_CHOICES


GAME_MIX_CHOICES = [("Half story, half action", "0.5"), ("Mostly action", "0.2"), ("Mostly story", "0.8"),
                    ("Only action", "0"), ("Only story", "1")]
CAPTION_POSITION_CHOICES = [("Normal height", "default"), ("Top", "top"), ("Middle", "middle"), ("Bottom", "bottom"), ("No captions (the video already has subtitles)", "off")]
CAPTION_SIZE_CHOICES = [("Normal", "default"), ("Small", "small"), ("Large", "large"), ("Extra large", "xlarge")]


GAME_FRAMING_CHOICES = [("Automatic (looks at the video)", "auto"), ("Whole picture over blurred bars (keeps the HUD and subtitles)", "fit"),
                        ("Full-screen portrait crop (may cut the HUD)", "crop")]


def game_args(game=False, mix="0.5", framing="auto"):
    """`--content game` (story AND action moments, whole picture kept in frame) with the story/action mix."""
    if not game:
        return []
    try:
        share = max(0.0, min(1.0, float(mix)))
    except (TypeError, ValueError):
        share = 0.5
    out = ["--content", "game", "--game_mix", f"{share:g}"]
    if framing in ("fit", "crop"):
        out += ["--game_framing", framing]
    return out


def caption_look_args(position="default", size="default"):
    """`--caption_position` / `--caption_size`, only when they differ from the normal look."""
    out = []
    if position in ("top", "middle", "bottom", "off"):
        out += ["--caption_position", position]
    if size in ("small", "large", "xlarge"):
        out += ["--caption_size", size]
    return out


def edit_args(style, strength="medium"):
    """`--auto_edit STYLE --edit_strength S` (nothing when no style is chosen)."""
    if not style or style == "none":
        return []
    return ["--auto_edit", style, "--edit_strength", strength if strength in ("subtle", "medium", "hyped") else "medium"]


# (label, name of the .env key the engine reads, where to get a key, note) for the "AI-written titles" box
LLM_KEY_PROVIDERS = {
    "groq": ("Groq (free, no card)", "GROQ_API_KEY", "https://console.groq.com", "sign in, then API Keys"),
    "gemini": ("Google Gemini (free tier)", "GEMINI_API_KEY", "https://aistudio.google.com/apikey", "sign in with a Google account"),
    "huggingface": ("Hugging Face", "HF_API_KEY", "https://huggingface.co/settings/tokens", "create a token with read access"),
    "openrouter": ("OpenRouter", "OPENROUTER_API_KEY", "https://openrouter.ai/keys", "some models are free"),
    "deepseek": ("DeepSeek (paid, cheap)", "DEEPSEEK_API_KEY", "https://platform.deepseek.com/api_keys", "needs a little credit"),
    "openai": ("OpenAI (paid)", "OPENAI_API_KEY", "https://platform.openai.com/api-keys", "needs credit"),
    "anthropic": ("Anthropic Claude (paid)", "ANTHROPIC_API_KEY", "https://console.anthropic.com/settings/keys", "needs credit"),
}
LLM_KEY_CHOICES = [(v[0], k) for k, v in LLM_KEY_PROVIDERS.items()]


def llm_key_help(provider):
    """One line telling where to get the key for `provider` (empty for an unknown one)."""
    item = LLM_KEY_PROVIDERS.get(provider)
    return f"Get a key at [{item[2].split('//')[1]}]({item[2]}) ({item[3]}), paste it below and save." if item else ""


def llm_key_env_name(provider):
    item = LLM_KEY_PROVIDERS.get(provider)
    return item[1] if item else None


COLOR_GRADE_CHOICES = [
    ("Automatic (the Auto-edit style decides; none without one)", "default"), ("None", "none"),
    ("Let the AI choose for this video", "auto"), ("Teal and orange (film look)", "teal_orange"),
    ("Cinematic warm", "cinematic_warm"), ("Vibrant action", "vibrant_action"), ("HDR pop", "hdr_pop"),
    ("Moody and dark", "moody_dark"), ("Cold thriller", "cold_thriller"), ("Cyberpunk", "cyberpunk"),
    ("Anime vivid", "anime_vivid"), ("Vintage VHS", "vintage_vhs"), ("Black and white film (Kurosawa)", "kurosawa"),
    ("Sepia western", "sepia_western"), ("Matrix green", "matrix_green")]
_GRADE_VALUES = {value for _label, value in COLOR_GRADE_CHOICES}


def grade_args(grade):
    """`--video_filter NAME` for a colour grade picked in the browser. 'default' / empty adds nothing, so the Auto-edit style's own grade
    (if any) still applies; an explicit choice, including 'none', wins over it."""
    if not grade or grade == "default" or grade not in _GRADE_VALUES:
        return []
    return ["--video_filter", grade]


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


DUB_ORIGINAL_CHOICES = [("Remove the original voice, keep the music and effects (recommended)", "music"),
                        ("Keep all of it very quiet under the new voice", "quiet"),
                        ("Lower it only while the new voice speaks", "duck"), ("Remove the original sound completely", "mute")]


def dub_args(source, target_lang, spoken="auto", burn_captions=False, session_dir=None, tts_provider="auto", voice="auto",
             original="music"):
    """Arguments (after the pipeline command) for `--mode DUB`. 'auto' voice / provider leave the flags out."""
    args = ["--mode", "DUB", "--source_video", source, "--target_lang", target_lang,
            "--language", (spoken or "auto")]
    if burn_captions:
        args.append("--dub_captions")
    if voice in ("female", "male"):
        args += ["--dub_voice", voice]
    if original in ("quiet", "duck", "mute"):
        args += ["--dub_original", original]          # "music" is the command line's default
    if tts_provider and tts_provider != "auto":
        args += ["--tts_provider", tts_provider]
    if session_dir:
        args += ["--session_dir", session_dir]
    return args


MAX_RECAP_SECONDS = 3600      # a wedding film can run 20-30 minutes; the engine itself has no limit

RECAP_KIND_CHOICES = [("Trip (days, places named from GPS)", "trip"), ("Wedding (one part per event of the day)", "wedding"),
                      ("Event or party", "event"), ("Family memories", "family")]
# what each kind changes in the form: (name label, parts label + example, note label + example)
RECAP_KIND_TEXT = {
    "trip": ("Trip name", "Stops (optional): one per line or comma separated, e.g. Pinemere Lake, Larkwater Lake", "A note about the trip (optional)"),
    "wedding": ("Names or title (optional)", "Parts of the day in the order they happened, e.g. Getting ready, Ceremony, Dinner, Dancing",
                "A note (optional): who is getting married, what each part was, favourite moments"),
    "event": ("Event name", "Parts of the event in order (optional), e.g. Arrival, Cake, Dancing", "A note about the event (optional)"),
    "family": ("Title (optional)", "Parts in order (optional), e.g. Summer, Diwali, New Year", "A note (optional): who is in the videos, what happened"),
}


def recap_kind_labels(kind):
    """(name label, parts label, note label) for the chosen kind of recap."""
    return RECAP_KIND_TEXT.get(kind) or RECAP_KIND_TEXT["trip"]


RECAP_SAMPLE_CHOICES = [("Automatic: weddings and events sample big folders, trips look at everything", "auto"),
                        ("Sample: about 3 videos per shot, spread over the whole folder (fast)", "3"),
                        ("Sample: about 6 videos per shot (more choice, slower)", "6"),
                        ("All videos (thorough: every file is read once, much slower for hundreds of videos)", "all")]

RECAP_GRADE_CHOICES =[("Automatic: a look only if the footage suits, otherwise none", "default")] + COLOR_GRADE_CHOICES[1:]


def trip_args(videos, session_dir, name="", stops="", note="", hook="", length=60, style="hype", music=None, look=False, both=False, name_places=True, enhance=False, kind="trip", keep_sound=False,
              grade="default", edit="none", edit_strength="medium", clean_sound=False, sample="auto", transitions="auto", subject_look="auto", subject_color="auto", subject_max=2, lines="", open_result=False):
    """Arguments (after the pipeline command) for `--mode TRIP`. Empty options are left out.
    look: also look at the pictures (--visual_context: better captions, sideways clips turned upright); both: a portrait and a landscape
    recap; name_places: name the places from the videos' GPS (rounded coordinates go to OpenStreetMap; off = --recap_no_geocode)."""
    args = ["--mode", "TRIP", "--trip_videos", *[str(v) for v in videos], "--session_dir", session_dir,
            "--recap_length", str(max(20, min(MAX_RECAP_SECONDS, int(length or 60))))]
    for flag, value in (("--trip_name", name), ("--trip_stops", stops), ("--user_context", note), ("--recap_hook", hook)):
        if (value or "").strip():
            args += [flag, value.strip()]
    if style == "plain":
        args += ["--recap_style", "plain"]
    if music:
        args += ["--music", str(music)]
    if look:
        args += ["--visual_context"]
    if both:
        args += ["--recap_versions", "both"]
    if not name_places:
        args += ["--recap_no_geocode"]
    if enhance:
        args += ["--enhance", "auto"]
    if kind in ("wedding", "event", "family"):
        args += ["--recap_kind", kind]
    if keep_sound:
        args += ["--recap_keep_sound"]
    args += grade_args(grade) + edit_args(edit, edit_strength)
    if clean_sound:
        args += ["--clean_audio"]
    if sample and str(sample) != "auto":
        args += ["--recap_sample", str(sample)]
    if transitions and str(transitions) != "auto":
        args += ["--transitions", str(transitions)]
    if subject_look and str(subject_look) != "auto":
        args += ["--subject_look", str(subject_look)]
    if subject_color and str(subject_color) != "auto":
        args += ["--subject_color", str(subject_color)]
    if subject_max is not None and int(subject_max) != 2:
        args += ["--subject_max", str(int(subject_max))]
    if (lines or "").strip():
        args += ["--recap_lines", "|".join(l.strip() for l in lines.splitlines() if l.strip())]
    if open_result:
        args += ["--recap_open_result"]
    return args


def find_trip_outputs(session_dir):
    """(recap video, itinerary .md) in a trip session folder; either is None when missing. With both versions the portrait recap
    is the one returned (find_trip_videos lists them all)."""
    videos = find_trip_videos(session_dir)
    for name in ("itinerary.md", os.path.join("portrait", "itinerary.md"), os.path.join("landscape", "itinerary.md")):
        md = os.path.join(session_dir, name)
        if os.path.isfile(md):
            return (videos[0] if videos else None, md)
    return (videos[0] if videos else None, None)


def find_trip_videos(session_dir):
    """Every finished recap video of a trip session: recap.mp4, or recap_portrait.mp4 and recap_landscape.mp4 (portrait first)."""
    names = ("recap.mp4", "recap_portrait.mp4", "recap_landscape.mp4")
    return [p for p in (os.path.join(session_dir, n) for n in names) if os.path.isfile(p)]


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
