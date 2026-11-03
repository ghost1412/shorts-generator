"""Fast word captions for long-form highlight reels.

The MoviePy path composited one image layer per word on every frame (24 minutes for a 4 minute reel). Here the words are
written to an ASS subtitle file and burned in with a single FFmpeg pass, which takes seconds.
"""
import os
import re
import shutil
import subprocess


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
_FONT_FILES = [os.path.join(_FONT_DIR, "NotoSansDevanagari.ttf"), os.path.join(_FONT_DIR, "NotoSansCyrillic.ttf")]


def _clean(word):
    word = re.sub(r"[{}\\]", "", word).upper()
    if _DEVANAGARI.search(word):
        # Impact has no Devanagari glyphs; name the bundled font so it does not depend on a system fallback
        word = "{\\fn" + DEVANAGARI_FONT + "}" + word
    return word


def _stage_fonts(folder):
    """Copy the bundled Devanagari/Cyrillic fonts next to the .ass file so `ass=...:fontsdir=.` finds them on any machine."""
    for font_file in _FONT_FILES:
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
    lines = [f"Dialogue: 0,{_ts(s)},{_ts(e)},Default,,0,0,0,,{_clean(t)}" for s, e, t in words]
    return head + "\n".join(lines) + "\n"


def burn_captions(video_in, ass_path, video_out, codec="libx264", quality_params=None):
    """Burn `ass_path` into `video_in` with FFmpeg (audio copied). Returns True on success."""
    exe = shutil.which("ffmpeg")
    if not exe:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
    folder, name = os.path.split(os.path.abspath(ass_path))
    _stage_fonts(folder)
    params = quality_params or (["-crf", "18"] if codec == "libx264" else ["-rc", "vbr", "-cq", "18", "-b:v", "0"])
    cmd = [exe, "-y", "-i", os.path.abspath(video_in), "-vf", f"ass={name}:fontsdir=.", "-c:v", codec, *params,
           "-pix_fmt", "yuv420p", "-c:a", "copy", os.path.abspath(video_out)]
    # relative file name + cwd: avoids Windows drive-letter escaping problems inside the filter string
    r = subprocess.run(cmd, cwd=folder, capture_output=True, text=True)
    return r.returncode == 0 and os.path.exists(video_out) and os.path.getsize(video_out) > 1000


def render_reel(paths, durations, out_path, xf=0.25, ass_path=None, codec="libx264", quality_params=None, workdir=None):
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
    vcur, acur, elapsed = "v0", "a0", durations[0]
    for i in range(1, n):
        if xf:
            parts.append(f"[{vcur}][v{i}]xfade=transition=fade:duration={xf}:offset={elapsed - xf:.3f}[xv{i}]")
            parts.append(f"[{acur}][a{i}]acrossfade=d={xf}:c1=tri:c2=tri[xa{i}]")
            elapsed += durations[i] - xf
        else:
            parts.append(f"[{vcur}][{acur}][v{i}][a{i}]concat=n=2:v=1:a=1[xv{i}][xa{i}]")
            elapsed += durations[i]
        vcur, acur = f"xv{i}", f"xa{i}"
    cwd = None
    if ass_path:
        cwd, name = os.path.split(os.path.abspath(ass_path))
        _stage_fonts(cwd)
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
    cmd += ["-filter_complex_script", script, "-map", f"[{vcur}]", "-map", f"[{acur}]", "-c:v", codec, *params,
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", os.path.abspath(out_path)]
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 1000
