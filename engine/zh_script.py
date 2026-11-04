"""Simplified / Traditional Chinese for the captions (`--zh_script simplified|traditional|auto`).

Whisper writes Chinese in whichever script it likes (Traditional for a Simplified speaker is common). `auto` leaves
its output alone; `simplified` / `traditional` convert the word-timed transcript with OpenCC before the captions
and the titles are made. Words are converted one by one, so the caption timing is untouched.

OpenCC is an optional extra (`pip install "shortsflow[zh]"`). Without it the run goes on with Whisper's own script
and says so.
"""
import copy
import json
import re

CHOICES = ("auto", "simplified", "traditional")
_CONFIG = {"simplified": "t2s", "traditional": "s2t"}
_HAN = re.compile(r"[㐀-䶿一-鿿]")
_MISSING = ('Converting the Chinese script needs one more package. Run:  pip install "shortsflow[zh]"  '
            "(the captions keep Whisper's own script for now).")


def resolve_script(value):
    """'simplified' / 'traditional' / 'auto'. Accepts short forms (s, t, zh-cn, zh-tw, hans, hant). Raises ValueError."""
    text = (value or "auto").strip().lower().replace("_", "-")
    aliases = {"s": "simplified", "hans": "simplified", "zh-cn": "simplified", "zh-hans": "simplified", "sc": "simplified",
               "t": "traditional", "hant": "traditional", "zh-tw": "traditional", "zh-hant": "traditional", "tc": "traditional"}
    text = aliases.get(text, text)
    if text not in CHOICES:
        raise ValueError(f"--zh_script must be one of {', '.join(CHOICES)} (got '{value}').")
    return text


def _converter(script):
    """OpenCC converter for the script, or None when the package is not installed."""
    try:
        from opencc import OpenCC
    except ImportError:
        return None
    return OpenCC(_CONFIG[script]).convert


def has_han(text):
    return bool(_HAN.search(text or ""))


def convert_text(text, script, convert=None):
    """`text` in the wanted script. Text without Chinese characters, and script 'auto', come back unchanged."""
    if script == "auto" or not has_han(text):
        return text
    convert = convert or _converter(script)
    if convert is None:
        raise RuntimeError(_MISSING)
    return convert(text)


def convert_transcript(transcript_path, script, convert=None):
    """Write `<transcript>_<script>.json` (segment text + every word converted) and return its path.
    Returns the original path for 'auto', for a transcript with no Chinese characters, and (with a warning) when
    OpenCC is not installed."""
    script = resolve_script(script)
    if script == "auto":
        return transcript_path
    with open(transcript_path, encoding="utf-8") as f:
        data = json.load(f)
    texts = [data.get("text") or ""] + [s.get("text") or "" for s in data.get("segments") or []]
    if not any(has_han(t) for t in texts):
        return transcript_path
    convert = convert or _converter(script)
    if convert is None:
        print(f"[Warning] {_MISSING}")
        return transcript_path
    result = copy.deepcopy(data)
    result["text"] = convert(result.get("text") or "")
    for seg in result.get("segments") or []:
        seg["text"] = convert(seg.get("text") or "")
        for w in seg.get("words") or []:
            if "word" in w:
                w["word"] = convert(w["word"])
    for w in result.get("words") or []:
        if "word" in w:
            w["word"] = convert(w["word"])
    out_path = re.sub(r"\.json$", "", transcript_path) + f"_{script}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    print(f"[Log] Chinese captions converted to {script} characters.")
    return out_path


def convert_highlights(highlights, script, convert=None):
    """Titles/hooks the AI wrote for the moments, in the same script (in place; no-op when nothing can be converted)."""
    script = resolve_script(script)
    if script == "auto":
        return highlights
    convert = convert or _converter(script)
    if convert is None:
        return highlights
    for h in highlights:
        for key in ("hook_text", "reason", "title"):
            if isinstance(h.get(key), str):
                h[key] = convert_text(h[key], script, convert)
    return highlights
