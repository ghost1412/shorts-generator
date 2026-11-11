"""A simple timeline strip for one finished short (logic only; the browser app shows the HTML).

The strip is the whole source video. The short being edited is a bright block, the other shorts of the same run are
dim blocks, and words cut out of the short are red marks inside it. Plain data in, a string out, so it is testable
without Gradio or a video.
"""
import html

MIN_LENGTH = 1.0


def source_length(words, cards):
    """Best guess of the source video's length: the latest word or short end (the results file has no duration)."""
    ends = [w["end"] for w in words if w.get("end") is not None]
    ends += [c["end"] for c in cards if c.get("end") is not None]
    return max(ends) if ends else 0.0


def nudge(value, delta, other, is_start, total=None):
    """Move a start (is_start) or end by `delta` seconds, keeping at least MIN_LENGTH between them and inside the video."""
    if value is None:
        return value
    new = round(float(value) + delta, 1)
    new = max(0.0, new)
    if total:
        new = min(new, round(total, 1))
    if other is not None:
        other = float(other)
        new = min(new, other - MIN_LENGTH) if is_start else max(new, other + MIN_LENGTH)
        new = max(0.0, new)
    return round(new, 1)


def _pct(x, total):
    return max(0.0, min(100.0, 100.0 * x / total))


def _clock(seconds):
    s = int(round(seconds))
    return f"{s // 60}:{s % 60:02d}"


def timeline_html(start, end, cuts, total, others=()):
    """HTML for the strip. `others` are (start, end) of the run's other shorts. Empty string when there is nothing to draw."""
    if start is None or end is None or not total or total <= 0 or end <= start:
        return ""
    total = max(total, end)

    def block(a, b, cls, title):
        left = _pct(a, total)
        width = max(0.4, _pct(b, total) - left)
        return f'<div class="sf-tl-{cls}" style="left:{left:.2f}%;width:{width:.2f}%" title="{html.escape(title)}"></div>'

    parts = [block(a, b, "other", f"Another short {_clock(a)}-{_clock(b)}") for a, b in others if a is not None and b is not None]
    parts.append(block(start, end, "clip", f"This short {_clock(start)}-{_clock(end)}"))
    parts += [block(a, b, "cut", f"Cut {a:.1f}-{b:.1f} s") for a, b in (cuts or []) if end >= a and b >= start]
    style = (
        "<style>.sf-tl{position:relative;height:34px;border-radius:6px;background:rgba(128,128,128,.25);overflow:hidden}"
        ".sf-tl div{position:absolute;top:0;bottom:0}"
        ".sf-tl-other{background:rgba(128,128,128,.55)}"
        ".sf-tl-clip{background:#3b82f6;opacity:.9}"
        ".sf-tl-cut{background:#ef4444;top:8px!important;bottom:8px!important}"
        ".sf-tl-legend{display:flex;justify-content:space-between;font-size:.8em;opacity:.8;margin-top:4px}</style>"
    )
    legend = (f'<div class="sf-tl-legend"><span>0:00</span><span>Blue: this short ({_clock(start)} to {_clock(end)}) · '
              f'red: cut words · grey: your other shorts</span><span>{_clock(total)}</span></div>')
    return f'{style}<div class="sf-tl">{"".join(parts)}</div>{legend}'
