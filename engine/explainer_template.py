"""Explainer videos from a fixed set of Manim scenes, timed to the narration.

The AI-written Manim code (`--mode EXPLAINER`) is hit and miss with small local models: scenes that freeze after a few seconds, boxes
with no text, animations that end long before the voice does. This builder does not ask a model for code. You give it beats; each beat
has the sentence to say and one of a few ready-made visuals. The narration is voiced first, every beat is timed from the word
timestamps, and the scene is generated so each visual lasts exactly as long as its sentence.

    beats = [
      {"kind": "title",   "say": "...", "title": "LHCb at CERN", "lines": ["Evidence of a rare decay"]},
      {"kind": "counter", "say": "...", "label": "1 in 10 billion", "total": 10_000_000_000},
      {"kind": "sigma",   "say": "...", "value": 3.2, "needed": 5.0},
      {"kind": "scale",   "say": "...", "levels": [["an atom", "10^-10 m"], ["a nucleus", "10^-15 m"], ["the zeptoverse", "10^-21 m"]]},
      {"kind": "bullets", "say": "...", "lines": ["first point", "second point"]},
    ]
"""
import json
import os
import re
import subprocess
import sys

KINDS = ("title", "counter", "sigma", "scale", "bullets")


def _sup(text):
    """'10^-15 m' -> '10⁻¹⁵ m' (Text() has no LaTeX)."""
    table = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")
    return re.sub(r"\^(-?\d+)", lambda m: m.group(1).translate(table), text)


def beat_times(beats, words, total):
    """[(start, end)] for each beat from the voice's word timestamps.

    Beats take the words in order: beat k owns as many words as its `say` has. When the voice's word list does not match the text
    (numbers, hyphens) the split is proportional to characters instead."""
    counts = [max(1, len(b["say"].split())) for b in beats]
    if words and abs(len(words) - sum(counts)) <= max(2, 0.05 * sum(counts)):
        scale = len(words) / sum(counts)
        edges, acc = [0.0], 0.0
        for c in counts[:-1]:
            acc += c * scale
            edges.append(float(words[min(len(words) - 1, int(round(acc)))]["start"]))
    else:
        chars = [max(1, len(b["say"])) for b in beats]
        edges, acc = [0.0], 0.0
        for c in chars[:-1]:
            acc += c
            edges.append(total * acc / sum(chars))
    edges.append(float(total))
    return [(edges[i], edges[i + 1]) for i in range(len(beats))]


HEADER = '''from manim import *

W = config.frame_width
H = W * config.pixel_height / config.pixel_width      # the visible height: manim keeps frame_height at 8 for a vertical render
K = H / 8.0                                           # vertical layout numbers below were written for a height of 8
BG = "#0b1020"
ACCENT = "#ffd166"
BLUE_ = "#4cc9f0"
RED_ = "#ef476f"
GREEN_ = "#06d6a0"


class ExplainerScene(Scene):
    def setup(self):
        self.camera.background_color = BG
        self._t = 0.0

    def P(self, *anims, run_time=1.0):
        self.play(*anims, run_time=run_time)
        self._t += run_time

    def until(self, t):
        gap = t - self._t
        if gap > 0.03:
            self.wait(gap)
            self._t += gap

    def clear_all(self):
        if self.mobjects:
            self.P(*[FadeOut(m) for m in list(self.mobjects)], run_time=0.4)

    def fit(self, m, frac=0.88):
        if m.width > W * frac:
            m.scale(W * frac / m.width)
        return m

    def construct(self):
'''


def _beat_code(kind, b, end):
    """Python source (indented 8 spaces) that shows this beat and ends it at scene time `end`."""
    q = lambda s: json.dumps(str(s), ensure_ascii=False)        # noqa: E731
    if kind == "title":
        lines = [str(x) for x in b.get("lines", [])]
        return (f"        t = self.fit(Text({q(b.get('title', ''))}, font_size=102, weight=BOLD, color=ACCENT)).shift(UP*(1.2*K))\n"
                f"        subs = VGroup(*[self.fit(Text(s, font_size=57, color=WHITE)) for s in {lines!r}]).arrange(DOWN, buff=0.35).next_to(t, DOWN, buff=0.7)\n"
                "        self.P(FadeIn(t, shift=UP*(0.3*K)), run_time=0.8)\n"
                "        self.P(LaggedStart(*[FadeIn(s, shift=UP*(0.2*K)) for s in subs], lag_ratio=0.4), run_time=1.2)\n"
                f"        self.until({end:.2f})\n")
    if kind == "counter":
        total = int(b.get("total", 10_000_000_000))
        return (f"        grid = VGroup(*[Dot(radius=0.05, color=BLUE_) for _ in range(200)]).arrange_in_grid(rows=10, cols=20, buff=0.16)\n"
                "        grid.scale_to_fit_width(W*0.86).shift(UP*(1.2*K))\n"
                "        hit = grid[137]\n"
                "        self.P(FadeIn(grid, lag_ratio=0.01), run_time=1.2)\n"
                f"        num = ValueTracker(0)\n"
                "        counter = always_redraw(lambda: self.fit(Text(f'{int(num.get_value()):,}', font_size=91, color=ACCENT, weight=BOLD)).shift(DOWN*(2.2*K)))\n"
                f"        cap = self.fit(Text({q(b.get('label', ''))}, font_size=68, color=WHITE)).shift(DOWN*(3.3*K))\n"
                "        self.add(counter)\n"
                f"        self.P(num.animate.set_value({total}), run_time=min(3.0, max(1.0, ({end:.2f} - self._t) * 0.45)))\n"
                "        counter.clear_updaters()\n"
                "        self.P(hit.animate.set_color(RED_).scale(3.2), FadeIn(cap), run_time=0.9)\n"
                f"        self.until({end:.2f})\n")
    if kind == "sigma":
        value, needed = float(b.get("value", 3.2)), float(b.get("needed", 5.0))
        return (f"        L = Line(LEFT*W*0.4, RIGHT*W*0.4, color=GREY_B).shift(UP*(0.4*K))\n"
                f"        x = lambda s: L.get_left() + (L.get_right() - L.get_left()) * (s / {needed})\n"
                "        ticks = VGroup(*[VGroup(Line(x(s)+DOWN*(0.12*K), x(s)+UP*(0.12*K), color=GREY_B), "
                "Text(str(s), font_size=44, color=GREY_B).next_to(x(s)+DOWN*(0.12*K), DOWN, buff=0.1)) for s in range(0, int(" + str(needed) + ")+1)])\n"
                "        head = self.fit(Text('How sure is it?', font_size=74, weight=BOLD, color=WHITE)).shift(UP*(3.0*K))\n"
                "        unit = Text('sigma', font_size=44, color=GREY_B).next_to(L, RIGHT, buff=0.1).shift(DOWN*(0.0*K))\n"
                "        self.P(FadeIn(head), Create(L), FadeIn(ticks), run_time=1.2)\n"
                f"        bar = Line(L.get_left(), x({value}), color=ACCENT, stroke_width=14).shift(UP*(0*K))\n"
                f"        lab = self.fit(Text('{value} sigma: evidence', font_size=64, color=ACCENT, weight=BOLD)).shift(DOWN*(1.4*K))\n"
                "        self.P(Create(bar), run_time=1.6)\n"
                "        self.P(FadeIn(lab), run_time=0.6)\n"
                f"        goal = DashedLine(x({needed})+UP*(1.0*K), x({needed})+DOWN*(0.6*K), color=GREEN_)\n"
                f"        glab = self.fit(Text('{needed:g} sigma needed to call it a discovery', font_size=51, color=GREEN_)).shift(DOWN*(2.6*K))\n"
                "        self.P(Create(goal), FadeIn(glab), run_time=1.0)\n"
                f"        self.until({end:.2f})\n")
    if kind == "scale":
        levels = [[_sup(str(a)), _sup(str(c))] for a, c in b.get("levels", [])]
        return (f"        levels = {levels!r}\n"
                "        head = self.fit(Text('Zooming in', font_size=74, weight=BOLD, color=WHITE)).shift(UP*(3.2*K))\n"
                "        self.P(FadeIn(head), run_time=0.5)\n"
                "        n = len(levels)\n"
                "        radii = [min(W, H*0.5)*0.42 * (0.45 ** i) for i in range(n)]\n"
                "        cols = [BLUE_, GREEN_, RED_, ACCENT]\n"
                "        rings = []\n"
                f"        per = max(1.0, ({end:.2f} - self._t - 0.8) / max(1, n))\n"
                "        for i, (name, size) in enumerate(levels):\n"
                "            ring = Circle(radius=radii[i], color=cols[i % 4], stroke_width=6).shift(UP*(0.2*K))\n"
                "            text = VGroup(self.fit(Text(name, font_size=61, color=cols[i % 4], weight=BOLD)), "
                "self.fit(Text(size, font_size=57, color=WHITE))).arrange(DOWN, buff=0.15).shift(DOWN*(2.2 + 0.0))\n"
                "            self.P(*( [FadeOut(rings[-1][1])] if rings else [] ), Create(ring), FadeIn(text), run_time=min(1.4, per*0.5))\n"
                "            rings.append((ring, text))\n"
                "            self.until(self._t + max(0.0, per - min(1.4, per*0.5)))\n"
                f"        self.until({end:.2f})\n")
    if kind == "bullets":
        lines = [str(x) for x in b.get("lines", [])]
        return (f"        head = self.fit(Text({q(b.get('title', 'Why it matters'))}, font_size=78, weight=BOLD, color=ACCENT)).shift(UP*(3.0*K))\n"
                f"        items = VGroup(*[self.fit(Text('• ' + s, font_size=57, color=WHITE), 0.9) for s in {lines!r}]).arrange(DOWN, aligned_edge=LEFT, buff=0.7).shift(DOWN*(0.3*K))\n"
                "        self.P(FadeIn(head), run_time=0.6)\n"
                f"        gap = max(0.8, ({end:.2f} - self._t - 0.6) / max(1, len(items)))\n"
                "        for it in items:\n"
                "            self.P(FadeIn(it, shift=RIGHT*0.3), run_time=0.7)\n"
                "            self.until(self._t + max(0.0, gap - 0.7))\n"
                f"        self.until({end:.2f})\n")
    raise ValueError(f"unknown beat kind '{kind}' (use one of {', '.join(KINDS)})")


def build_scene_code(beats, times):
    """Python source of an ExplainerScene showing every beat for its time slot."""
    parts = [HEADER]
    for i, (b, (start, end)) in enumerate(zip(beats, times)):
        parts.append(f"        # beat {i + 1}: {b['kind']}\n        self.until({start:.2f})\n")
        parts.append(_beat_code(b["kind"], b, end))
        if i < len(beats) - 1:
            parts.append("        self.clear_all()\n")
    parts.append("        self.until(self._t + 0.6)\n")
    return "".join(parts)


def media_seconds(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def make_explainer(beats, session_dir, extract_mode="shorts", voice="en-US-AvaNeural", rate="+0%", voice_fn=None, render_fn=None):
    """Voice the beats, time them, render the scene and mux. Returns the final mp4 path."""
    for b in beats:
        if b.get("kind") not in KINDS or not str(b.get("say", "")).strip():
            raise ValueError(f"every beat needs a 'say' sentence and a kind from {KINDS}: {b}")
    os.makedirs(session_dir, exist_ok=True)
    narration = " ".join(b["say"].strip() for b in beats)
    if voice_fn is None:
        from engine.voice_gen import generate_voice
        voice_fn = lambda text, a, s: generate_voice(text, output_audio=a, output_subs=s, voice_name=voice, rate=rate, add_cta=False)  # noqa: E731
    audio = os.path.join(session_dir, "voice.mp3")
    subs = os.path.join(session_dir, "subs.json")
    voice_fn(narration, audio, subs)
    if not os.path.isfile(audio):
        raise RuntimeError("The narration could not be voiced.")
    total = media_seconds(audio)
    try:
        with open(subs, "r", encoding="utf-8") as f:
            words = json.load(f)
    except (OSError, ValueError):
        words = []
    times = beat_times(beats, words, total)
    code = build_scene_code(beats, times)
    with open(os.path.join(session_dir, "template_scene.py"), "w", encoding="utf-8") as f:
        f.write(code)
    if render_fn is None:
        from engine.video_gen import render_manim_scene
        render_fn = lambda c: render_manim_scene(c, session_dir, extract_mode=extract_mode)  # noqa: E731
    video = render_fn(code)
    out = os.path.join(session_dir, "final_explainer.mp4")
    v_dur = media_seconds(video)
    # the picture is held on its last frame if it is shorter than the voice; the file ends when the voice ends
    cmd = ["ffmpeg", "-y", "-i", video, "-i", audio, "-vf", f"tpad=stop_mode=clone:stop_duration={max(0.0, total - v_dur) + 1:.2f}",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-t", f"{total + 0.4:.2f}", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(out):
        raise RuntimeError("FFmpeg could not combine the picture and the voice: " + (r.stderr or "")[-400:])
    print(f"[Log] Explainer ready: {out} ({total:.1f}s voice, {v_dur:.1f}s picture)")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: python -m engine.explainer_template beats.json session_dir [shorts|long]")
        sys.exit(2)
    with open(sys.argv[1], "r", encoding="utf-8") as fh:
        make_explainer(json.load(fh), sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "shorts")
