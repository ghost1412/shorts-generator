"""Click-to-cut words for one finished short (logic only; the browser app draws the tick boxes).

The browser app shows the words of a short's transcript as tick boxes. Ticked words are cut out of the short
when it is re-rendered (``engine.rerender --cuts``). Everything here works on plain data so it can be tested
without Gradio or a video.
"""
import json
import os
import re

from engine import transcript_edit

MAX_WORDS = 400   # a short is at most 3 minutes; more words than this means the window is wrong


def load_words(session_dir):
    """Every timed word of the run's transcript, in order: [{'word', 'start', 'end'}]. Empty when there is none."""
    path = os.path.join(session_dir, "transcript.json")
    try:
        with open(path, encoding="utf-8") as f:
            return transcript_edit.flatten_words(json.load(f).get("segments", []))
    except (OSError, ValueError, AttributeError):
        return []


def _inside(word, spans):
    mid = (word["start"] + word["end"]) / 2
    return any(s <= mid < e for s, e in spans)


def window_words(words, start, end):
    """[(index, word)] for the words of the transcript spoken inside [start, end]; `index` is the position in `words`."""
    if start is None or end is None:
        return []
    out = [(i, w) for i, w in enumerate(words) if start <= (w["start"] + w["end"]) / 2 <= end]
    return out[:MAX_WORDS]


def choices_for(words, start, end, cuts=None):
    """(choices, ticked): `choices` is [(label, index)] for a checkbox group, `ticked` the indices already cut."""
    window = window_words(words, start, end)
    choices = [(w["word"], i) for i, w in window]
    ticked = [i for i, w in window if _inside(w, cuts or [])]
    return choices, ticked


def _key(text):
    """Comparison form that also works for non-Latin scripts: lower-case letters and digits of any script."""
    return re.sub(r"[\W_]+", "", (text or "").lower())


def phrase_ticks(words, window, phrase):
    """Indices (positions in `words`) of every occurrence of `phrase` among the window's words, for the 'select phrase' box.

    `window` is the list of word indices the tick boxes show. Matching ignores case and punctuation and works without
    spaces (Chinese / Japanese words are 1-3 characters), by joining whole words until the phrase length is reached."""
    target = _key(phrase)
    if not target:
        return []
    window = [i for i in window if 0 <= i < len(words)]
    found = []
    for a in range(len(window)):
        joined = ""
        for b in range(a, len(window)):
            joined += _key(words[window[b]]["word"])
            if joined == target:
                found.extend(window[a:b + 1])
                break
            if len(joined) >= len(target) or not target.startswith(joined):
                break
    return sorted(set(found))


def spans_from_ticks(words, ticked):
    """Padded, merged [(start, end)] source-second spans for the ticked word indices (neighbouring words become one cut)."""
    idx = sorted({int(i) for i in ticked or [] if 0 <= int(i) < len(words)})
    ranges, run = [], None
    for i in idx:
        if run and i == run[1]:
            run[1] = i + 1
        else:
            run = [i, i + 1]
            ranges.append(run)
    return transcript_edit._spans(words, [tuple(r) for r in ranges])


def spans_arg(spans):
    """Command-line form of the cut spans: '1.2:1.8,3.0:3.5' (empty string = no cuts)."""
    return ",".join(f"{s:.3f}:{e:.3f}" for s, e in spans)


def parse_spans_arg(text):
    """Inverse of `spans_arg`; ValueError with a plain reason for anything else."""
    spans = []
    for part in (text or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            a, b = part.split(":")
            s, e = float(a), float(b)
        except ValueError:
            raise ValueError("Cuts must look like 1.2:1.8,3.0:3.5 (seconds in the original video).")
        if e > s >= 0:
            spans.append((s, e))
    from engine.fillers import merge_spans
    return merge_spans(spans)


def summary(spans):
    """One plain line about what the cuts remove."""
    if not spans:
        return "Nothing is cut."
    secs = sum(e - s for s, e in spans)
    return f"{len(spans)} cut{'s' if len(spans) != 1 else ''}, {secs:.1f} s removed."
