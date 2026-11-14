"""Fast word captions for long-form highlight reels.

The MoviePy path composited one image layer per word on every frame (24 minutes for a 4 minute reel). Here the words are
written to an ASS subtitle file and burned in with a single FFmpeg pass, which takes seconds.
"""
import os
import re
import shutil
import subprocess

from engine.script_fonts import ARABIC_FONT, SUBSET_DIR, cjk_language, cjk_subset, has_arabic, subset_files_for


def reel_words(parts, transcript_data, xf=0.0):
    """Words on the REEL timeline. `parts` = [(start, end, duration)] for each segment in play order (source seconds and
    the rendered segment length); consecutive segments overlap by `xf` seconds (the crossfade)."""
    words, offset = [], 0.0
    for start, _end, duration in parts:
        for seg in transcript_data.get("segments", []):
            for w in seg.get("words") or []:
                text = (w.get("word") or "").strip()
                if not text or "start" not in w or "end" not in w:
                    continue
                ws, we = float(w["start"]) - start, float(w["end"]) - start
                if we <= 0 or ws >= duration:
                    continue
                words.append((offset + max(0.0, ws), offset + min(duration, max(we, ws + 0.12)), text))
        offset += duration - xf
    words.sort(key=lambda t: t[0])
    # never show two words at once: a word ends when the next begins
    fixed = []
    for i, (s, e, t) in enumerate(words):
        if i + 1 < len(words):
            e = min(e, words[i + 1][0])
        if e - s >= 0.04:
            fixed.append((s, e, t))
    return fixed


def _ts(seconds):
    cs = int(round(seconds * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


_DEVANAGARI = re.compile("[ऀ-ॿ]")
DEVANAGARI_FONT = "Noto Sans Devanagari"
_CYRILLIC_GREEK = re.compile("[Ͱ-ϿЀ-ԯ]")
CYRILLIC_FONT = "Noto Sans"
_FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "remotion-video", "public", "fonts")
_FONT_FILES = [os.path.join(_FONT_DIR, "NotoSansDevanagari.ttf"), os.path.join(_FONT_DIR, "NotoSansCyrillic.ttf"),
               os.path.join(_FONT_DIR, "NotoSansArabic.ttf")]


def _clean(word, cjk_family=None, upper=True, tag_cyrillic=False):
    """ASS-safe text with a `{\\fn...}` font override for scripts Impact cannot draw. `upper`/`tag_cyrillic` are for
    sentence captions (dubbing): keep the case and also name the bundled font for Cyrillic/Greek."""
    word = re.sub(r"[{}\\]", "", word)
    if upper:
        word = word.upper()
    if cjk_family and cjk_language(word):
        # Chinese/Japanese/Korean: per-transcript subset font from engine.script_fonts (named here, staged next to the .ass)
        word = "{\\fn" + cjk_family + "}" + word
    elif has_arabic(word):
        # libass shapes and reorders Arabic itself (HarfBuzz/FriBidi); each Dialogue holds one word, so word order is moot
        word = "{\\fn" + ARABIC_FONT + "}" + word
    elif _DEVANAGARI.search(word):
        # Impact has no Devanagari glyphs; name the bundled font so it does not depend on a system fallback
        word = "{\\fn" + DEVANAGARI_FONT + "}" + word
    elif tag_cyrillic and _CYRILLIC_GREEK.search(word):
        word = "{\\fn" + CYRILLIC_FONT + "}" + word
    return word


def _stage_fonts(folder, ass_path=None):
    """Copy the bundled Devanagari/Cyrillic/Arabic fonts (and any CJK subset the .ass names) next to the .ass file so
    `ass=...:fontsdir=.` finds them on any machine."""
    extra = []
    if ass_path:
        try:
            with open(ass_path, encoding="utf-8") as f:
                extra = subset_files_for(f.read(), SUBSET_DIR)
        except OSError:
            pass
    for font_file in _FONT_FILES + extra:
        try:
            if os.path.exists(font_file):
                dest = os.path.join(folder, os.path.basename(font_file))
                if not os.path.exists(dest):
                    shutil.copyfile(font_file, dest)
        except OSError:
            pass


def ass_document(words, size=(1920, 1080), font="Impact", font_size=None, bottom_margin=None):
    w, h = size
    font_size = font_size or round(h * 0.075)
    bottom_margin = bottom_margin if bottom_margin is not None else round(h * 0.17)
    head = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {w}\nPlayResY: {h}\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
        "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font},{font_size},&H0000F5FF,&H0000F5FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,"
        f"{max(3, round(h / 270))},1,2,40,40,{bottom_margin},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    subset = cjk_subset(" ".join(t for _s, _e, t in words))  # None unless the words contain Chinese/Japanese/Korean
    family = subset[0] if subset else None
    lines = [f"Dialogue: 0,{_ts(s)},{_ts(e)},Default,,0,0,0,,{_clean(t, family)}" for s, e, t in words]
    return head + "\n".join(lines) + "\n"


def burn_captions(video_in, ass_path, video_out, codec="libx264", quality_params=None):
    """Burn `ass_path` into `video_in` with FFmpeg (audio copied). Returns True on success."""
    exe = shutil.which("ffmpeg")
    if not exe:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
    folder, name = os.path.split(os.path.abspath(ass_path))
    _stage_fonts(folder, ass_path)
    params = quality_params or (["-crf", "18"] if codec == "libx264" else ["-rc", "vbr", "-cq", "18", "-b:v", "0"])
    cmd = [exe, "-y", "-i", os.path.abspath(video_in), "-vf", f"ass={name}:fontsdir=.", "-c:v", codec, *params,
           "-pix_fmt", "yuv420p", "-c:a", "copy", os.path.abspath(video_out)]
    # relative file name + cwd: avoids Windows drive-letter escaping problems inside the filter string
    r = subprocess.run(cmd, cwd=folder, capture_output=True, text=True)
    return r.returncode == 0 and os.path.exists(video_out) and os.path.getsize(video_out) > 1000


def render_reel(paths, durations, out_path, xf=0.25, ass_path=None, codec="libx264", quality_params=None, workdir=None, transitions=None):
    """Join `paths` into one reel with FFmpeg: crossfades (xfade / acrossfade) and, optionally, burned-in ASS captions, all in
    one encode. MoviePy needed ~14 minutes for the same 5 minute reel because it re-composites every frame. Returns True on success.
    `durations` are the rendered lengths of the segments (same order)."""
    n = len(paths)
    if n == 0 or n != len(durations):
        return False
    exe = shutil.which("ffmpeg")
    if not exe:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
    xf = xf if n > 1 and all(d > 2 * xf for d in durations) else 0.0
    parts = []
    for i in range(n):
        parts.append(f"[{i}:v]fps=30,setsar=1,format=yuv420p[v{i}]")
        parts.append(f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}]")
    names = list(transitions or [])
    vcur, acur, elapsed = "v0", "a0", durations[0]
    for i in range(1, n):
        if xf:
            kind = names[i - 1] if i - 1 < len(names) else "fade"
            parts.append(f"[{vcur}][v{i}]xfade=transition={kind}:duration={xf}:offset={elapsed - xf:.3f}[xv{i}]")
            parts.append(f"[{acur}][a{i}]acrossfade=d={xf}:c1=tri:c2=tri[xa{i}]")
            elapsed += durations[i] - xf
        else:
            parts.append(f"[{vcur}][{acur}][v{i}][a{i}]concat=n=2:v=1:a=1[xv{i}][xa{i}]")
            elapsed += durations[i]
        vcur, acur = f"xv{i}", f"xa{i}"
    cwd = None
    if ass_path:
        cwd, name = os.path.split(os.path.abspath(ass_path))
        _stage_fonts(cwd, ass_path)
        parts.append(f"[{vcur}]ass={name}:fontsdir=.[vout]")
        vcur = "vout"
    folder = workdir or cwd or os.path.dirname(os.path.abspath(out_path))
    script = os.path.join(folder, "reel_filter.txt")
    with open(script, "w", encoding="utf-8") as f:
        f.write(";\n".join(parts))
    params = quality_params or (["-crf", "18"] if codec == "libx264" else ["-rc", "vbr", "-cq", "18", "-b:v", "0"])
    cmd = [exe, "-y"]
    for p in paths:
        cmd += ["-i", os.path.abspath(p)]
    from engine.ffmpeg_compat import filter_complex_script_args
    cmd += [*filter_complex_script_args(exe, script), "-map", f"[{vcur}]", "-map", f"[{acur}]", "-c:v", codec, *params,
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", os.path.abspath(out_path)]
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 1000


def clip_seconds(path):
    """Length of a video file in seconds (ffprobe), None when it cannot be read."""
    exe = shutil.which("ffprobe")
    if not exe:
        return None
    try:
        r = subprocess.run([exe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", os.path.abspath(path)],
                           capture_output=True, text=True, timeout=60)
        return float(r.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def join_clips(paths, out_path, transition="auto", codec="libx264", quality_params=None):
    """One reel from finished clips of the same size (for example the vertical shorts of one run), joined with crossfades or the chosen
    transition look. Returns out_path, None when fewer than two clips could be read or FFmpeg failed. The clips themselves are untouched."""
    from engine.transitions import xfade_names
    paths = [p for p in paths if p and os.path.isfile(p)]
    durations = [clip_seconds(p) for p in paths]
    keep = [(p, d) for p, d in zip(paths, durations) if d]
    if len(keep) < 2:
        return None
    paths, durations = [k[0] for k in keep], [k[1] for k in keep]
    ok = render_reel(paths, durations, out_path, codec=codec, quality_params=quality_params,
                     workdir=os.path.dirname(os.path.abspath(out_path)), transitions=xfade_names(transition, len(paths) - 1))
    return out_path if ok else None
