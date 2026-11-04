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
CHARS_PER_SECOND = 14.0   # rough spoken rate, tells the LLM how long a translation may be
BATCH = 20
SOFT_SPEEDUP = 1.35       # speed-up allowed to fit the segment's own time slot
HARD_SPEEDUP = 1.6        # speed-up allowed when borrowing the silence before the next segment


def normalize_lang(code):
    return str(code or "").strip().lower().replace("_", "-").split("-")[0]


def supported_languages():
    return sorted(EDGE_VOICES)


def voice_for(lang):
    return EDGE_VOICES.get(normalize_lang(lang))


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


def translate_segments(segments, target_lang, llm=None, parse=None):
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
            "so stay at or below max_chars when you can. Do not merge or split lines.\n\n"
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


def has_audio(path):
    import imageio_ffmpeg
    err = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", path], capture_output=True, text=True).stderr
    return bool(re.search(r"Stream #.*Audio", err))


def synthesize(text, lang, out_path, provider="auto"):
    """Speak `text` to an audio file. edge-tts by default; local Kokoro (English only) when asked for or as fallback."""
    lang = normalize_lang(lang)
    if provider == "kokoro" and lang == "en":
        from engine import kokoro_tts
        if kokoro_tts.is_available():
            kokoro_tts.generate_voice_kokoro(text, out_path, out_path + ".json", download=False)
            return out_path
    voice = voice_for(lang)
    if not voice:
        raise ValueError(f"No voice for language '{lang}'. Supported: {', '.join(supported_languages())}")
    try:
        import asyncio
        import edge_tts
        asyncio.run(edge_tts.Communicate(text, voice).save(out_path))
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


def build_filter(placements, total, source_has_audio=True):
    """FFmpeg filter_complex text. placements: [{index(input no.), start, tempo, trim}] with inputs 1..n = dub clips."""
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
    if source_has_audio:
        parts.append(mix + ",asplit=2[dubmix][dubkey]")
        parts.append("[0:a]aresample=44100[orig]")
        parts.append("[orig][dubkey]sidechaincompress=threshold=0.015:ratio=14:attack=15:release=500:makeup=1[ducked]")
        parts.append("[ducked][dubmix]amix=inputs=2:normalize=0:duration=first[aout]")
    else:
        parts.append(mix + "[aout]")
    return ";\n".join(parts)


def mix_dub(source_video, clips, output_path, session_dir, burn_srt=None):
    """clips: [{path, start, tempo, trim}]. Writes output_path (video copied, new audio; re-encoded if captions burn in)."""
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    total = media_duration(source_video) or (max(c["start"] for c in clips) + 5)
    placements = [dict(c, index=i) for i, c in enumerate(clips, 1)]
    script = os.path.join(session_dir, "dub_filter.txt")
    with open(script, "w", encoding="utf-8") as f:
        f.write(build_filter(placements, total, has_audio(source_video)))
    cmd = [ffmpeg, "-y", "-i", os.path.abspath(source_video)]
    for c in clips:
        cmd += ["-i", os.path.abspath(c["path"])]
    cmd += ["-filter_complex_script", os.path.abspath(script), "-map", "0:v:0", "-map", "[aout]"]
    if burn_srt:
        cmd += ["-vf", f"subtitles={os.path.basename(burn_srt)}:force_style='FontSize=18,Outline=2,MarginV=40'",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
    else:
        cmd += ["-c:v", "copy"]
    cmd += ["-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", os.path.abspath(output_path)]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=session_dir if burn_srt else None)
    if res.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError("FFmpeg dub mix failed: " + (res.stderr or "")[-600:])
    return output_path


def dub_video(source_video, target_lang, session_dir, output_path=None, language="en", provider="auto",
              captions=False, transcribe=None, llm=None, synth=None, mixer=None, workers=4):
    """Full pipeline. Returns {"video", "srt", "json", "segments", "failed_translations", "failed_voices"}.
    transcribe/llm/synth/mixer can be replaced (tests, custom backends)."""
    target = normalize_lang(target_lang)
    if target not in EDGE_VOICES:
        raise ValueError(f"Unsupported dub language '{target_lang}'. Supported: {', '.join(supported_languages())}")
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

    texts, failed_tr = translate_segments(segments, target, llm=llm)
    if failed_tr == len(segments):
        raise RuntimeError("Translation failed for every segment (no LLM answered). Check your AI key / Ollama "
                           "(see `shortsflow doctor`); nothing was dubbed.")
    translated = [dict(s, text=t) for s, t in zip(segments, texts)]

    synth = synth or (lambda text, out: synthesize(text, target, out, provider))
    clips_dir = os.path.join(session_dir, "dub_clips")
    os.makedirs(clips_dir, exist_ok=True)

    def make(i):
        path = os.path.join(clips_dir, f"seg_{i:04d}.mp3")
        try:
            synth(texts[i], path)
            return path if os.path.exists(path) else None
        except Exception as e:
            print(f"[Warning] Voice for segment {i + 1} failed: {e}")
            return None

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        paths = list(pool.map(make, range(len(segments))))
    failed_voice = sum(1 for p in paths if not p)
    if failed_voice == len(paths):
        raise RuntimeError("No voice could be generated (edge-tts needs internet; Kokoro covers English only).")

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
    json_path = os.path.join(session_dir, f"{base}_{target}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"target_lang": target, "source_lang": source_lang, "segments": translated}, f, ensure_ascii=False, indent=2)

    output_path = output_path or os.path.join(session_dir, f"{base}_dub_{target}.mp4")
    (mixer or mix_dub)(source_video, clips, output_path, session_dir, burn_srt=srt_path if captions else None)
    return {"video": output_path, "srt": srt_path, "json": json_path, "segments": len(segments),
            "failed_translations": failed_tr, "failed_voices": failed_voice}
