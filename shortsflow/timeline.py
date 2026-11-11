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
    for cls, at, tip in (("hs", start, "Drag to move the start"), ("he", end, "Drag to move the end")):
        parts.append(f'<div class="sf-tl-h sf-tl-{cls}" data-t="{at:.1f}" style="left:{_pct(at, total):.2f}%" title="{tip}"></div>')
    style = (
        "<style>.sf-tl{position:relative;height:34px;border-radius:6px;background:rgba(128,128,128,.25);overflow:hidden}"
        ".sf-tl div{position:absolute;top:0;bottom:0}"
        ".sf-tl-other{background:rgba(128,128,128,.55)}"
        ".sf-tl-clip{background:#3b82f6;opacity:.9}"
        ".sf-tl-h{width:12px;margin-left:-6px;background:#1d4ed8;cursor:ew-resize;touch-action:none;z-index:2;border-radius:3px}"
        ".sf-tl-cut{background:#ef4444;top:8px!important;bottom:8px!important}"
        ".sf-tl-legend{display:flex;justify-content:space-between;font-size:.8em;opacity:.8;margin-top:4px}</style>"
    )
    legend = (f'<div class="sf-tl-legend"><span>0:00</span><span>Blue: this short ({_clock(start)} to {_clock(end)}) · '
              f'red: cut words · grey: your other shorts</span><span>{_clock(total)}</span></div>')
    return f'{style}<div class="sf-tl" data-total="{total:.2f}">{"".join(parts)}</div>{legend}'


def nudge_view(start, end, delta, is_start, total, cuts=None, others=()):
    """(start, end, strip_html) after one Start/End button press, so the boxes and the strip move together."""
    if is_start:
        start = nudge(start, delta, end, True, total)
    else:
        end = nudge(end, delta, start, False, total)
    return start, end, timeline_html(start, end, cuts, total, others)


# Runs once when the page loads (gr.Blocks load event). Dragging a blue handle moves it on screen; letting go writes the
# seconds into the Start/End box, and the box's change event redraws the strip and keeps the 1 s minimum.
DRAG_JS = """() => {
  if (window.__sfTl) return; window.__sfTl = true;
  let d = null;
  const secs = (e) => { const r = d.strip.getBoundingClientRect(); return Math.max(0, Math.min(d.total, (e.clientX - r.left) / r.width * d.total)); };
  document.addEventListener('pointerdown', (e) => {
    const h = e.target.closest && e.target.closest('.sf-tl-h'); if (!h) return;
    const strip = h.closest('.sf-tl'); d = {h, strip, total: parseFloat(strip.dataset.total), start: h.classList.contains('sf-tl-hs')};
    h.setPointerCapture && h.setPointerCapture(e.pointerId); e.preventDefault();
  });
  document.addEventListener('pointermove', (e) => { if (d) d.h.style.left = (secs(e) / d.total * 100) + '%'; });
  document.addEventListener('pointerup', (e) => {
    if (!d) return; const other = parseFloat(d.strip.querySelector(d.start ? '.sf-tl-he' : '.sf-tl-hs').dataset.t); let t = Math.round(secs(e) * 10) / 10; t = d.start ? Math.min(t, other - 1) : Math.max(t, other + 1); t = Math.max(0, Math.min(d.total, t)); const want = d.start ? 'Start (seconds' : 'End (seconds';
    let node = d.strip, input = null;
    while (node && !input) { node = node.parentElement; if (!node) break;
      for (const l of node.querySelectorAll('label')) { if ((l.textContent || '').trim().startsWith(want)) { input = l.querySelector('input'); break; } } }
    d = null; if (!input) return;
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    set.call(input, String(t)); input.dispatchEvent(new Event('input', {bubbles: true})); input.dispatchEvent(new Event('change', {bubbles: true}));
  });
}"""
