"""AI dubbing: transcribe -> translate per segment -> synthesise -> time-fit -> mix over ducked original audio.

First version, deliberately simple: one synthetic voice per language (no voice cloning, no per-speaker voices),
sentence-level timing taken from the Whisper segments, translation by the normal LLM chain.
"""
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

MODE = "DUB"

LANG_NAMES = {
    "es": "Spanish", "hi": "Hindi", "de": "German", "fr": "French", "ja": "Japanese", "pt": "Portuguese",
    "zh": "Chinese", "it": "Italian", "ru": "Russian", "ko": "Korean", "ar": "Arabic", "en": "English",
    "tr": "Turkish", "nl": "Dutch", "pl": "Polish", "uk": "Ukrainian", "id": "Indonesian",
}
EDGE_VOICES = {
    "es": "es-ES-ElviraNeural", "hi": "hi-IN-SwaraNeural", "de": "de-DE-KatjaNeural", "fr": "fr-FR-DeniseNeural",
    "ja": "ja-JP-NanamiNeural", "pt": "pt-BR-FranciscaNeural", "zh": "zh-CN-XiaoxiaoNeural",
    "it": "it-IT-ElsaNeural", "ru": "ru-RU-SvetlanaNeural", "ko": "ko-KR-SunHiNeural", "ar": "ar-SA-ZariyahNeural",
    "en": "en-US-AvaNeural", "tr": "tr-TR-EmelNeural", "nl": "nl-NL-ColetteNeural", "pl": "pl-PL-ZofiaNeural",
    "uk": "uk-UA-PolinaNeural", "id": "id-ID-GadisNeural",
}
EDGE_VOICES_MALE = {
    "es": "es-ES-AlvaroNeural", "hi": "hi-IN-MadhurNeural", "de": "de-DE-ConradNeural", "fr": "fr-FR-HenriNeural",
    "ja": "ja-JP-KeitaNeural", "pt": "pt-BR-AntonioNeural", "zh": "zh-CN-YunxiNeural",
    "it": "it-IT-DiegoNeural", "ru": "ru-RU-DmitryNeural", "ko": "ko-KR-InJoonNeural", "ar": "ar-SA-HamedNeural",
    "en": "en-US-AndrewNeural", "tr": "tr-TR-AhmetNeural", "nl": "nl-NL-MaartenNeural", "pl": "pl-PL-MarekNeural",
    "uk": "uk-UA-OstapNeural", "id": "id-ID-ArdiNeural",
}
VOICE_NAME_RE = re.compile(r"^[a-z]{2,3}-[A-Z]{2}-[A-Za-z]+Neural$")
CHARS_PER_SECOND = 14.0   # rough spoken rate, tells the LLM how long a translation may be
BATCH = 20
SOFT_SPEEDUP = 1.35       # speed-up allowed to fit the segment's own time slot
HARD_SPEEDUP = 1.6        # speed-up allowed when borrowing the silence before the next segment


def normalize_lang(code):
    return str(code or "").strip().lower().replace("_", "-").split("-")[0]


def supported_languages():
    return sorted(EDGE_VOICES)


def voice_for(lang, voice=None):
    """Default edge-tts voice for `lang`. `voice` overrides it: "female" / "male" pick that gender's default voice for
    the language, a full name such as "es-ES-AlvaroNeural" is used as given (anything else raises ValueError)."""
    lang = normalize_lang(lang)
    choice = str(voice or "").strip()
    if choice.lower() in ("", "auto", "female"):
        return EDGE_VOICES.get(lang)
    if choice.lower() == "male":
        return EDGE_VOICES_MALE.get(lang)
    if VOICE_NAME_RE.match(choice):
        return choice
    raise ValueError(f"Unknown voice '{voice}'. Use male, female or a full edge-tts name like es-ES-AlvaroNeural "
                     f"(run `edge-tts --list-voices` to see them).")


def srt_time(seconds):
    ms = int(round(max(0.0, seconds) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(segments):
    """segments: [{start, end, text}] -> SRT text."""
    blocks = []
    for i, seg in enumerate(segments, 1):
        blocks.append(f"{i}\n{srt_time(seg['start'])} --> {srt_time(seg['end'])}\n{seg['text'].strip()}\n")
    return "\n".join(blocks)


def coverage_warning(segments, video_seconds, threshold=0.4):
    """A sentence when speech recognition found speech in only a small part of the video (the rest keeps its original voice),
    else None. Typical causes: a language the model is weak at, mixed languages, music or game sound over the voice."""
    if not video_seconds or video_seconds < 5 or not segments:
        return None
    spoken = sum(max(0.0, float(s["end"]) - float(s["start"])) for s in segments)
    if spoken / video_seconds >= threshold:
        return None
    return (f"Speech recognition found speech in only {spoken:.0f} s of the {video_seconds:.0f} s video, so the rest keeps its original "
            "voice. For other languages or mixed languages try a bigger speech model (set SHORTSFLOW_WHISPER_MODEL=large-v3) and "
            "pick the spoken language instead of 'detect automatically'.")


def voice_failure_message(errors):
    """The error shown when no segment got a voice: names the real cause when it is the common 403 (Microsoft rejects an old
    edge-tts), otherwise the generic hint."""
    text = " ".join(errors or [])
    if "403" in text or "Invalid response status" in text:
        return ("The voice service (Microsoft Edge TTS) rejected the request, which usually means the installed 'edge-tts' "
                "package is too old. Update it with:  pip install -U edge-tts  (use the same Python that runs ShortsFlow), then try again.")
    return "No voice could be generated (edge-tts needs internet; Kokoro covers English only)."


def segments_from_transcript(data, min_len=0.4):
    """Whisper segments -> [{start, end, text}] without empty / sub-0.4 s ones."""
    out = []
    for seg in (data or {}).get("segments", []):
        text = str(seg.get("text", "")).strip()
        start, end = float(seg.get("start", 0)), float(seg.get("end", 0))
        if text and end - start >= min_len:
            out.append({"start": start, "end": end, "text": text})
    return out


def _default_llm(prompt):
    from engine.script_gen import get_llm_response
    return get_llm_response(prompt, system_prompt="You are a professional dubbing translator. Return raw JSON only.")


def _parse(response):
    from engine.script_gen import robust_json_parse
    return robust_json_parse(response)


TONES = {
    "faithful": "",                       # the default: keep the speaker's own tone, exactly the old behaviour
    "funny": "Rewrite each line in a playful, funny tone, with light jokes where they fit, but keep the meaning and every fact.",
    "sarcastic": "Rewrite each line in a dry, sarcastic tone, as if the speaker is rolling their eyes, but keep the meaning and every fact.",
    "dramatic": "Rewrite each line in an intense, dramatic, trailer-voice tone, but keep the meaning and every fact.",
    "formal": "Rewrite each line in a polite, formal, professional tone, but keep the meaning and every fact.",
    "casual": "Rewrite each line in relaxed, casual, everyday street talk, but keep the meaning and every fact.",
}
TONE_CHOICES = [("Faithful (the speaker's own tone)", "faithful"), ("Funny", "funny"), ("Sarcastic", "sarcastic"),
                ("Dramatic", "dramatic"), ("Formal", "formal"), ("Casual", "casual")]

# speed and pitch of the computer voice (edge-tts takes rate and pitch, not real emotions): neutral = the voice's own delivery
DELIVERIES = {"neutral": None, "excited": ("+12%", "+3Hz"), "calm": ("-8%", "-2Hz"), "serious": ("-5%", "-4Hz")}
DELIVERY_CHOICES = [("Neutral (the voice's own delivery)", "neutral"), ("Excited (faster, higher)", "excited"),
                    ("Calm (slower, softer)", "calm"), ("Serious (slower, lower)", "serious")]


def tone_line(tone):
    """The extra translation instruction for a tone, "" for faithful or an unknown name (the prompt is then unchanged)."""
    text = TONES.get((tone or "faithful").lower(), "")
    return text + "\n" if text else ""


def translate_segments(segments, target_lang, llm=None, parse=None, about=None, tone="faithful"):
    """Translate each segment keeping one-to-one timing. Returns (texts, failed_count).
    A segment the LLM did not return stays in the source language and counts as failed."""
    llm, parse = llm or _default_llm, parse or _parse
    lang_full = LANG_NAMES.get(normalize_lang(target_lang), target_lang)
    texts = [s["text"] for s in segments]
    failed = 0
    for lo in range(0, len(segments), BATCH):
        chunk = segments[lo:lo + BATCH]
        items = [{"id": lo + i, "text": s["text"],
                  "max_chars": max(12, int((s["end"] - s["start"]) * CHARS_PER_SECOND))} for i, s in enumerate(chunk)]
        prompt = (
            f"Translate each spoken line of this video into natural, spoken {lang_full} for dubbing.\n"
            "Keep the meaning and tone. Each translation must be short enough to be spoken in the same time, "
            "so stay at or below max_chars when you can. Do not merge or split lines.\n"
            "The lines come from speech recognition, so a word can be misheard: when a line makes no sense, translate what was "
            "most likely meant, and keep names as proper names.\n"
            + tone_line(tone)
            + (f"What the video is about (use it to fix misheard names and terms): {str(about).strip()[:400]}\n" if about else "") + "\n"
            f"Lines: {json.dumps(items, ensure_ascii=False)}\n\n"
            'Return raw JSON only: {"translations": [{"id": <id>, "text": "<translated line>"}]}'
        )
        got = {}
        try:
            data = parse(llm(prompt))
            rows = data.get("translations") if isinstance(data, dict) else data
            for row in rows or []:
                if isinstance(row, dict) and str(row.get("text", "")).strip():
                    got[int(row["id"])] = str(row["text"]).strip()
        except Exception as e:
            print(f"[Warning] Translation batch failed: {e}")
        for i in range(lo, lo + len(chunk)):
            if i in got:
                texts[i] = got[i]
            else:
                failed += 1
    return texts, failed


def plan_fit(tts_dur, preferred, hard):
    """Decide how to fit synthesised speech into the slot.
    preferred = the original segment length, hard = time until the next segment starts.
    Returns {"tempo": speed factor >= 1, "duration": resulting length, "trim": max length or None}."""
    preferred, hard = max(0.3, preferred), max(0.3, max(hard, preferred))
    tempo = 1.0
    if tts_dur > preferred:
        tempo = min(tts_dur / preferred, SOFT_SPEEDUP)
    if tts_dur / tempo > hard:
        tempo = min(tts_dur / hard, HARD_SPEEDUP)
    final = tts_dur / tempo
    return {"tempo": round(tempo, 3), "duration": final, "trim": hard if final > hard + 0.05 else None}


def media_duration(path):
    import imageio_ffmpeg
    err = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", path], capture_output=True, text=True).stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def video_size(path, default=(1280, 720)):
    """(width, height) of the first video stream, `default` when it cannot be read."""
    if not path or not os.path.exists(path):
        return default
    import imageio_ffmpeg
    err = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", path], capture_output=True, text=True).stderr
    for line in err.splitlines():
        if "Video:" in line:
            m = re.search(r"[,\s](\d{2,5})x(\d{2,5})[,\s\[]", line + " ")
            if m:
                return int(m.group(1)), int(m.group(2))
    return default


def _scoped_font(token):
    """A word that starts with a `{\\fn...}` override: scale the small-looking Devanagari / Arabic fonts up a little and
    `{\\r}` back to the style afterwards, so the Latin words that follow do not inherit that font."""
    if not token.startswith("{\\fn"):
        return token
    from engine import reel_captions as rc
    from engine.script_fonts import ARABIC_FONT
    end = token.index("}")
    scale = {rc.DEVANAGARI_FONT: 118, ARABIC_FONT: 120}.get(token[4:end])
    tag = token[:end] + (f"\\fscx{scale}\\fscy{scale}" if scale else "") + "}"
    return tag + token[end + 1:] + "{\\r}"


CAPTION_SIZES = {"small": 0.8, "default": 1.0, "large": 1.35, "xlarge": 1.7}
# (ASS alignment, bottom/top margin as a share of the frame height). "above" sits above the usual spot of subtitles that are
# already burned into the video, so the two lines do not print over each other.
CAPTION_POSITIONS = {"bottom": (2, 0.08), "above": (2, 0.2), "middle": (5, 0.0), "top": (8, 0.06)}


def build_ass(segments, size=(1280, 720), caption_size="default", caption_position="bottom"):
    """Sentence captions as an ASS document. Unlike the SRT `subtitles=` filter (one default font), each word that is
    Devanagari / Arabic / Cyrillic / Greek / Chinese / Japanese / Korean names a font that has its glyphs, so non-Latin
    dubs do not show empty boxes. The CJK font is a small per-transcript subset (downloaded once, see script_fonts)."""
    from engine import reel_captions as rc
    from engine.script_fonts import cjk_language, cjk_subset
    w, h = size
    font_size = round(min(w, h) * 0.06 * CAPTION_SIZES.get((caption_size or "default").lower(), 1.0))
    align, margin_v = CAPTION_POSITIONS.get((caption_position or "bottom").lower(), CAPTION_POSITIONS["bottom"])
    outline = max(2, round(font_size / 14))
    side = round(w * 0.06)
    head = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {w}\nPlayResY: {h}\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
        "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,Arial,{font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,"
        f"{outline},1,{align},{side},{side},{round(h * margin_v)},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    subset = cjk_subset(" ".join(seg["text"] for seg in segments))  # None unless the text has Chinese/Japanese/Korean
    family = subset[0] if subset else None
    # libass only breaks lines at spaces, and Chinese/Japanese have none: cut long CJK runs ourselves (a CJK glyph is
    # about one font size wide) so a sentence never runs off the frame.
    max_cjk = max(6, int((w - 2 * side) / font_size))
    lines = []
    for seg in segments:
        parts = []
        for tok in seg["text"].split():
            if family and len(tok) > max_cjk and cjk_language(tok):
                chunks = [tok[i:i + max_cjk] for i in range(0, len(tok), max_cjk)]
                parts.append("\\N".join(_scoped_font(rc._clean(c, family, upper=False)) for c in chunks))
            else:
                parts.append(_scoped_font(rc._clean(tok, family, upper=False, tag_cyrillic=True)))
        text = " ".join(parts)
        lines.append(f"Dialogue: 0,{rc._ts(seg['start'])},{rc._ts(seg['end'])},Default,,0,0,0,,{text}")
    return head + "\n".join(lines) + "\n"


def has_audio(path):
    import imageio_ffmpeg
    err = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", path], capture_output=True, text=True).stderr
    return bool(re.search(r"Stream #.*Audio", err))


def synthesize(text, lang, out_path, provider="auto", voice=None, delivery="neutral"):
    """Speak `text` to an audio file. edge-tts by default; local Kokoro (English only) when asked for or as fallback."""
    lang = normalize_lang(lang)
    if provider == "kokoro" and lang == "en":
        from engine import kokoro_tts
        if kokoro_tts.is_available():
            kokoro_tts.generate_voice_kokoro(text, out_path, out_path + ".json", download=False)
            return out_path
    voice_name = voice_for(lang, voice)
    if not voice_name:
        raise ValueError(f"No voice for language '{lang}'. Supported: {', '.join(supported_languages())}")
    try:
        import asyncio
        import edge_tts
        speed = DELIVERIES.get((delivery or "neutral").lower())
        talk = edge_tts.Communicate(text, voice_name, rate=speed[0], pitch=speed[1]) if speed else edge_tts.Communicate(text, voice_name)
        asyncio.run(talk.save(out_path))
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return out_path
        raise RuntimeError("edge-tts wrote no audio")
    except Exception as e:
        if lang == "en":
            from engine import kokoro_tts
            if kokoro_tts.is_available():
                print(f"[Warning] edge-tts failed ({e}); using local Kokoro.")
                kokoro_tts.generate_voice_kokoro(text, out_path, out_path + ".json", download=False)
                return out_path
        raise


ORIGINAL_MODES = ("music", "quiet", "duck", "mute")
QUIET_GAIN = 0.12            # about -18 dB: the original stays as a faint bed, the new voice is clearly in front


def build_filter(placements, total, source_has_audio=True, original="quiet", stem_index=None):
    """FFmpeg filter_complex text. placements: [{index(input no.), start, tempo, trim}] with inputs 1..n = dub clips.

    original: what happens to the video's own sound. "quiet" (default) keeps it at about -18 dB and lowers it further while the
    new voice speaks, "duck" only lowers it while the new voice speaks (the original stays at full volume elsewhere, so any part
    that was not dubbed is heard in the original language), "mute" removes it completely. "music" (needs `stem_index`, the input
    number of the voice-free stem from engine.stem_split) keeps the music and effects at full volume with the original voice removed."""
    parts, labels = [], []
    for p in placements:
        chain = []
        if p["tempo"] > 1.001:
            chain.append(f"atempo={p['tempo']:.3f}")
        if p.get("trim"):
            chain += [f"atrim=0:{p['trim']:.3f}", f"afade=t=out:st={max(0.0, p['trim'] - 0.08):.3f}:d=0.08"]
        delay = int(round(p["start"] * 1000))
        chain.append(f"adelay={delay}|{delay}")
        label = f"d{p['index']}"
        parts.append(f"[{p['index']}:a]" + ",".join(chain) + f"[{label}]")
        labels.append(f"[{label}]")
    n = len(labels)
    mix = "".join(labels) + f"amix=inputs={n}:normalize=0:dropout_transition=0,apad=whole_dur={total:.3f}"
    if source_has_audio and original != "mute":
        parts.append(mix + ",asplit=2[dubmix][dubkey]")
        if original == "music" and stem_index:
            parts.append(f"[{stem_index}:a]aresample=44100,volume=0.9[orig]")
        else:
            parts.append("[0:a]aresample=44100" + (f",volume={QUIET_GAIN}" if original in ("quiet", "music") else "") + "[orig]")
        parts.append("[orig][dubkey]sidechaincompress=threshold=0.015:ratio=14:attack=15:release=500:makeup=1[ducked]")
        parts.append("[ducked][dubmix]amix=inputs=2:normalize=0:duration=first[aout]")
    else:
        parts.append(mix + "[aout]")
    return ";\n".join(parts)


def mix_dub(source_video, clips, output_path, session_dir, burn_srt=None, original="quiet"):
    """clips: [{path, start, tempo, trim}]. Writes output_path (video copied, new audio; re-encoded if captions burn in)."""
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    total = media_duration(source_video) or (max(c["start"] for c in clips) + 5)
    placements = [dict(c, index=i) for i, c in enumerate(clips, 1)]
    stem = None
    if original == "music" and has_audio(source_video):
        from engine.stem_split import split_vocals
        stem = split_vocals(source_video, session_dir)         # None -> the faint-original fallback inside build_filter
    if len(clips) > CHUNK_CLIPS and _inputs_length(clips, session_dir) > MAX_INPUT_CHARS:
        # Windows refuses a command line over ~32,000 characters, and every dub clip is one input: mix the clips in batches
        # into a few long wav files first (the same placement, tempo and trim), then mix those with the original sound.
        merged = []
        for k in range(0, len(clips), CHUNK_CLIPS):
            merged.append({"path": _mix_batch(ffmpeg, source_video, clips[k:k + CHUNK_CLIPS], total, session_dir, k // CHUNK_CLIPS),
                           "start": 0.0, "tempo": 1.0, "trim": None})
        clips = merged
        placements = [dict(c, index=i) for i, c in enumerate(clips, 1)]
    script = os.path.join(session_dir, "dub_filter.txt")
    with open(script, "w", encoding="utf-8") as f:
        f.write(build_filter(placements, total, has_audio(source_video), original, stem_index=len(clips) + 1 if stem else None))
    cmd = [ffmpeg, "-y", "-i", os.path.abspath(source_video)]
    for c in clips:
        cmd += ["-i", _short_path(c["path"], session_dir)]     # relative to session_dir (the command runs there): far shorter
    if stem:
        cmd += ["-i", _short_path(stem, session_dir)]
    from engine.ffmpeg_compat import filter_complex_script_args
    cmd += [*filter_complex_script_args(ffmpeg, os.path.basename(script)), "-map", "0:v:0", "-map", "[aout]"]
    if burn_srt:
        ass = os.path.splitext(burn_srt)[0] + ".ass"
        if os.path.exists(ass):  # script-aware captions written by dub_video; staged fonts sit next to it
            from engine.reel_captions import _stage_fonts
            _stage_fonts(session_dir, ass)
            vf = f"ass={os.path.basename(ass)}:fontsdir=."
        else:
            vf = f"subtitles={os.path.basename(burn_srt)}:force_style='FontSize=18,Outline=2,MarginV=40'"
        cmd += ["-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
    else:
        cmd += ["-c:v", "copy"]
    cmd += ["-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", os.path.abspath(output_path)]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=session_dir)
    if res.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError("FFmpeg dub mix failed: " + (res.stderr or "")[-600:])
    return output_path


def _voice_matches(sidecar, tag):
    """True when a finished voice clip may be reused: its note says it was made from this text and delivery, or it has no note
    (a clip from before notes existed: kept, as it always was on a resume)."""
    try:
        with open(sidecar, "r", encoding="utf-8") as f:
            return f.read() == tag
    except FileNotFoundError:
        return True
    except OSError:
        return False


def saved_translation(json_path, target, segments, tone="faithful"):
    """The translated lines saved by an earlier run of this session, or None.
    Only used when it is the same language and has the same number of lines at the same times as the segments being dubbed now."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    saved = data.get("segments") if isinstance(data, dict) else None
    if data.get("target_lang") != target or not isinstance(saved, list) or len(saved) != len(segments):
        return None
    if (data.get("tone") or "faithful") != (tone or "faithful"):
        return None                                              # another tone asked for: translate again
    texts = []
    for old, new in zip(saved, segments):
        if not isinstance(old, dict) or not str(old.get("text", "")).strip():
            return None
        if abs(float(old.get("start", -1)) - float(new["start"])) > 0.05:
            return None
        texts.append(str(old["text"]))
    return texts


CHUNK_CLIPS = 120          # dub clips mixed per batch when the command line would be too long
MAX_INPUT_CHARS = 20000    # Windows allows about 32,000 characters in one command line; keep well below it


def _short_path(path, base):
    """`path` relative to `base` when that is possible and shorter (another drive cannot be relative on Windows), else absolute."""
    absolute = os.path.abspath(path)
    try:
        rel = os.path.relpath(absolute, os.path.abspath(base))
    except ValueError:
        return absolute
    return rel if len(rel) < len(absolute) else absolute


def _inputs_length(clips, session_dir):
    """Characters the `-i <clip>` arguments of all clips add to the command line."""
    return sum(len(_short_path(c["path"], session_dir)) + 4 for c in clips)


def _mix_batch(ffmpeg, source_video, clips, total, session_dir, number):
    """Mix a batch of dub clips (placed, tempo-fitted, trimmed) into one full-length wav; returns its path."""
    out = os.path.join(session_dir, f"dub_batch_{number}.wav")
    script = os.path.join(session_dir, f"dub_batch_{number}_filter.txt")
    with open(script, "w", encoding="utf-8") as f:
        f.write(build_filter([dict(c, index=i) for i, c in enumerate(clips, 1)], total, source_has_audio=False, original="mute"))
    cmd = [ffmpeg, "-y", "-i", os.path.abspath(source_video)]        # input 0 is only there to keep the clip numbering from 1
    for c in clips:
        cmd += ["-i", _short_path(c["path"], session_dir)]
    from engine.ffmpeg_compat import filter_complex_script_args
    cmd += [*filter_complex_script_args(ffmpeg, os.path.basename(script)), "-map", "[aout]", "-c:a", "pcm_s16le", "-t", f"{total:.3f}", os.path.basename(out)]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=session_dir)
    if res.returncode != 0 or not os.path.exists(out):
        raise RuntimeError("FFmpeg dub batch mix failed: " + (res.stderr or "")[-600:])
    return out


def dub_video(source_video, target_lang, session_dir, output_path=None, language="en", provider="auto",
              captions=False, transcribe=None, llm=None, synth=None, mixer=None, workers=4, voice=None, original="music", about=None,
              tone="faithful", delivery="neutral", caption_size="default", caption_position="bottom"):
    """Full pipeline. Returns {"video", "srt", "json", "segments", "failed_translations", "failed_voices"}.
    transcribe/llm/synth/mixer can be replaced (tests, custom backends)."""
    target = normalize_lang(target_lang)
    if target not in EDGE_VOICES:
        raise ValueError(f"Unsupported dub language '{target_lang}'. Supported: {', '.join(supported_languages())}")
    voice_for(target, voice)  # a bad --dub_voice fails here, before any transcription / LLM work is spent
    os.makedirs(session_dir, exist_ok=True)
    if transcribe is None:
        from engine.analysis import transcribe_video
        transcribe = lambda: transcribe_video(source_video, session_dir, language=language)  # noqa: E731
    with open(transcribe(), "r", encoding="utf-8") as f:
        data = json.load(f)
    source_lang = normalize_lang(data.get("language"))
    if source_lang == target:
        raise ValueError(f"The video is already in '{target}'; choose another --target_lang.")
    segments = segments_from_transcript(data)
    if not segments:
        raise ValueError("No speech found in the video, nothing to dub.")
    print(f"[Log] Dubbing {len(segments)} spoken segment(s) into {LANG_NAMES.get(target, target)}...")
    note = coverage_warning(segments, media_duration(source_video))
    if note:
        print(f"[Warning] {note}")

    base = os.path.splitext(os.path.basename(source_video))[0]
    json_path = os.path.join(session_dir, f"{base}_{target}.json")
    saved = saved_translation(json_path, target, segments, tone)         # an earlier run of this session already translated it
    if saved:
        texts, failed_tr = saved, 0
        print(f"[Log] Reusing the saved {LANG_NAMES.get(target, target)} translation ({len(texts)} lines) and any finished voice clips from "
              f"this session: no AI text or voice service is called for them. Delete {os.path.basename(json_path)} to translate again.")
    else:
        texts, failed_tr = translate_segments(segments, target, llm=llm, about=about, tone=tone)
    if failed_tr == len(segments):
        raise RuntimeError("Translation failed for every segment (no LLM answered). Check your AI key / Ollama "
                           "(see `shortsflow doctor`); nothing was dubbed.")
    translated = [dict(s, text=t) for s, t in zip(segments, texts)]
    with open(json_path, "w", encoding="utf-8") as f:              # saved right away: a crash later (voices, mix) keeps the translation
        json.dump({"target_lang": target, "source_lang": source_lang, "tone": tone or "faithful", "delivery": delivery or "neutral",
                   "segments": translated}, f, ensure_ascii=False, indent=2)

    if not synth:
        if (delivery or "neutral") == "neutral":       # the default keeps the exact old call (custom backends may not take `delivery`)
            synth = lambda text, out: synthesize(text, target, out, provider, voice)  # noqa: E731
        else:
            synth = lambda text, out: synthesize(text, target, out, provider, voice, delivery)  # noqa: E731
    clips_dir = os.path.join(session_dir, "dub_clips")
    os.makedirs(clips_dir, exist_ok=True)

    voice_errors = []

    def make(i):
        path = os.path.join(clips_dir, f"seg_{i:04d}.mp3")
        tag = f"{delivery or 'neutral'}\n{texts[i]}"      # what this clip was voiced from, kept next to it
        if saved and os.path.exists(path) and os.path.getsize(path) > 200 and _voice_matches(path + ".voice", tag):
            return path                                  # voiced by an earlier run on this same translation and delivery: keep it
        try:
            synth(texts[i], path)
            if os.path.exists(path) and os.path.getsize(path) > 200:
                try:
                    with open(path + ".voice", "w", encoding="utf-8") as f:
                        f.write(tag)
                except OSError:
                    pass
                return path
            raise RuntimeError("the voice service returned an empty file")
        except Exception as e:
            voice_errors.append(str(e))
            print(f"[Warning] Voice for segment {i + 1} failed: {e}")
            try:
                if os.path.exists(path) and os.path.getsize(path) <= 200:
                    os.remove(path)                      # an empty file must not look like a finished voice
            except OSError:
                pass
            return None

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        paths = list(pool.map(make, range(len(segments))))
    failed_voice = sum(1 for p in paths if not p)
    if failed_voice == len(paths):
        raise RuntimeError(voice_failure_message(voice_errors))

    clips = []
    for i, (seg, path) in enumerate(zip(segments, paths)):
        if not path:
            continue
        nxt = segments[i + 1]["start"] if i + 1 < len(segments) else seg["end"] + 3.0
        fit = plan_fit(media_duration(path), seg["end"] - seg["start"], nxt - seg["start"])
        clips.append({"path": path, "start": seg["start"], "tempo": fit["tempo"], "trim": fit["trim"]})

    base = os.path.splitext(os.path.basename(source_video))[0]
    srt_path = os.path.join(session_dir, f"{base}_{target}.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(build_srt(translated))
    if captions:
        with open(os.path.join(session_dir, f"{base}_{target}.ass"), "w", encoding="utf-8") as f:
            f.write(build_ass(translated, video_size(source_video), caption_size, caption_position))
    json_path = os.path.join(session_dir, f"{base}_{target}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"target_lang": target, "source_lang": source_lang, "tone": tone or "faithful", "delivery": delivery or "neutral",
                   "segments": translated}, f, ensure_ascii=False, indent=2)

    output_path = output_path or os.path.join(session_dir, f"{base}_dub_{target}.mp4")
    if mixer is None:
        mix_dub(source_video, clips, output_path, session_dir, burn_srt=srt_path if captions else None, original=original)
    else:
        mixer(source_video, clips, output_path, session_dir, burn_srt=srt_path if captions else None)
    return {"video": output_path, "srt": srt_path, "json": json_path, "segments": len(segments),
            "failed_translations": failed_tr, "failed_voices": failed_voice}
