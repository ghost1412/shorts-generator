"""Translate a word-timed Whisper transcript so the captions can be in another language.

The translated text of each segment is spread over the segment's own time span (by word length), so the
caption animation keeps following the speech even though the words are different.

Only languages the caption fonts can draw are offered: Latin-script languages (Anton), Hindi/Marathi
(Noto Sans Devanagari), Russian/Ukrainian/Bulgarian/Greek (Noto Sans), Arabic (bundled Noto Sans Arabic) and
Chinese/Japanese/Korean (Noto Sans CJK, downloaded once and cut down per render, see engine/script_fonts.py).
"""
import copy
import json
import os
import re

LANGUAGES = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German", "pt": "Portuguese", "it": "Italian",
    "nl": "Dutch", "pl": "Polish", "tr": "Turkish", "id": "Indonesian", "vi": "Vietnamese",
    "hi": "Hindi", "mr": "Marathi",
    "ru": "Russian", "uk": "Ukrainian", "bg": "Bulgarian", "el": "Greek",
    "ar": "Arabic", "zh": "Chinese", "ja": "Japanese", "ko": "Korean",
}
BATCH_SEGMENTS = 30
BATCH_CHARS = 3500


def resolve_language(value):
    """Language code from 'es' / 'Spanish' / 'spanish'. Raises ValueError (plain message) for unsupported ones."""
    text = (value or "").strip().lower()
    if text in LANGUAGES:
        return text
    for code, name in LANGUAGES.items():
        if text == name.lower():
            return code
    raise ValueError(f"Captions in '{value}' are not supported yet (the caption fonts cannot draw it). "
                     f"Supported: {', '.join(f'{n} ({c})' for c, n in LANGUAGES.items())}.")


def _batches(texts):
    batch, size = [], 0
    for i, text in texts:
        if batch and (len(batch) >= BATCH_SEGMENTS or size + len(text) > BATCH_CHARS):
            yield batch
            batch, size = [], 0
        batch.append((i, text))
        size += len(text)
    if batch:
        yield batch


def translate_lines(lines, language, ask):
    """{index: translated text} for [(index, text)]. Lines the AI skipped or garbled are left out (caller keeps the original)."""
    name = LANGUAGES[language]
    out = {}
    for batch in _batches(lines):
        numbered = "\n".join(f"{i}: {t}" for i, t in batch)
        prompt = (f"Translate each numbered subtitle line into {name}. Keep the meaning, a natural spoken style and about the same "
                  f"length; keep names as they are. Return ONLY a JSON object mapping each number (as a string) to its "
                  f"translation, for example {{\"3\": \"...\"}}.\n\n{numbered}")
        try:
            data = ask(prompt)
        except Exception as e:
            print(f"[Warning] Caption translation failed for one batch ({e}); those captions stay in the original language.")
            continue
        if not isinstance(data, dict):
            continue
        for i, _ in batch:
            value = data.get(str(i))
            if isinstance(value, str) and value.strip():
                out[i] = value.strip()
    return out


_CJK_UNIT = re.compile(r"[A-Za-z0-9_'’]+|\s+|.", re.S)
_CJK_CHUNK = 3  # characters per caption word for languages written without spaces
_CLOSERS = "，。！？、；：…,.!?;:)）」』”"


def caption_tokens(text):
    """Caption 'words' for `text`. Spaced languages split on whitespace. Chinese/Japanese have no spaces, so runs of
    CJK characters are cut into chunks of a few characters (closing punctuation stays with the chunk before it)."""
    from engine.script_fonts import cjk_language
    if cjk_language(text) not in ("zh", "ja"):  # Latin, Cyrillic, Arabic, ... and Korean (which uses spaces)
        return text.split()
    tokens, chunk = [], ""
    for unit in _CJK_UNIT.findall(text):
        if unit.isspace():
            if chunk:
                tokens.append(chunk)
                chunk = ""
        elif len(unit) > 1 or unit.isascii() and unit.isalnum():
            if chunk:
                tokens.append(chunk)
                chunk = ""
            tokens.append(unit)
        elif unit in _CLOSERS and (chunk or tokens):
            if chunk:
                tokens.append(chunk + unit)
                chunk = ""
            else:
                tokens[-1] += unit
        else:
            chunk += unit
            if len(chunk) >= _CJK_CHUNK:
                tokens.append(chunk)
                chunk = ""
    if chunk:
        tokens.append(chunk)
    return tokens


def respread(segment, new_text):
    """Word list for `new_text` timed across the span of the segment's original words."""
    words = [w for w in segment.get("words") or [] if "start" in w and "end" in w]
    t0 = words[0]["start"] if words else segment.get("start", 0.0)
    t1 = words[-1]["end"] if words else segment.get("end", t0)
    t1 = max(t1, t0 + 0.2)
    tokens = caption_tokens(new_text)
    if not tokens:
        return []
    weights = [len(t) + 1 for t in tokens]
    total = float(sum(weights))
    out, cursor = [], t0
    for token, weight in zip(tokens, weights):
        end = cursor + (t1 - t0) * weight / total
        out.append({"word": " " + token, "start": round(cursor, 3), "end": round(end, 3), "probability": 1.0})
        cursor = end
    return out


def translate_transcript(transcript_path, language, ask=None):
    """Write `<transcript>_<language>.json` next to the transcript and return its path (the original path when the
    video is already in that language). Segments the AI could not translate keep their original words."""
    language = resolve_language(language)
    with open(transcript_path, encoding="utf-8") as f:
        data = json.load(f)
    if (data.get("language") or "").lower().startswith(language):
        print(f"[Log] The video is already in {LANGUAGES[language]}; no caption translation needed.")
        return transcript_path
    out_path = re.sub(r"\.json$", "", transcript_path) + f"_{language}.json"
    if os.path.exists(out_path) and os.path.getmtime(out_path) >= os.path.getmtime(transcript_path):
        return out_path
    if ask is None:
        from engine.find_moments import llm_ask
        ask = llm_ask()
    segments = data.get("segments") or []
    lines = [(i, (s.get("text") or "").strip()) for i, s in enumerate(segments) if (s.get("text") or "").strip()]
    print(f"[Log] Translating {len(lines)} caption segments into {LANGUAGES[language]}...")
    done = translate_lines(lines, language, ask)
    if not done:
        raise RuntimeError("The captions could not be translated (no AI provider answered). "
                           "Add a free Groq key or start Ollama, or make the captions without translation.")
    result = copy.deepcopy(data)
    for i, seg in enumerate(result.get("segments") or []):
        if i in done:
            seg["text"] = " " + done[i]
            seg["words"] = respread(segments[i], done[i])
    result["text"] = " ".join(s.get("text", "").strip() for s in result.get("segments") or [])
    result["language"] = language
    missed = len(lines) - len(done)
    if missed:
        print(f"[Warning] {missed} caption segment(s) could not be translated and stay in the original language.")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    return out_path
