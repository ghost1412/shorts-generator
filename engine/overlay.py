"""Visual template and intro / outro covers on a LONG video (the highlights video).

A long video cannot be rendered frame by frame in the animated renderer (a 10 minute video is 18,000 frames), so only the pieces that
carry something are rendered there, as short transparent clips: the opening (the intro cover and the template's opening elements such
as a name tag) and the ending (the outro cover and the closing line). FFmpeg then lays them over the finished video in one encode.

Limits, stated plainly: the template's always-on elements (a progress bar, a frame, letterbox bars) appear in those two pieces only, not
for the whole video. The whole video is re-encoded once (video only; the audio is copied).
"""
import json
import os
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMOTION = os.path.join(ROOT, "remotion-video")
HEAD_SECONDS = 7.0       # the opening piece: long enough for the cover and a name tag (which fades out at 6.5 s)
TAIL_SECONDS = 3.0       # the ending piece: the outro cover and the closing line (the last 2.4 s)
MIN_TOTAL = 12.0         # a shorter video gets one piece over its whole length


def wanted(props):
    """True when the chosen props hold something to draw over a long video."""
    return bool(props.get("visualTemplate") or props.get("introAnimation") or props.get("outroAnimation"))


def plan(total, props):
    """[(start, seconds)] of the pieces to render for a video of `total` seconds."""
    pieces = []
    opening = bool(props.get("visualTemplate") or props.get("introAnimation"))
    ending = bool(props.get("visualTemplate") or props.get("outroAnimation"))
    if total < MIN_TOTAL:
        return [(0.0, round(total, 3))] if (opening or ending) else []
    if opening:
        pieces.append((0.0, HEAD_SECONDS))
    if ending:
        pieces.append((round(total - TAIL_SECONDS, 3), TAIL_SECONDS))
    return pieces


def probe(video):
    """(width, height, seconds) of a video file, or None."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
                        "-of", "json", video], capture_output=True, text=True)
    try:
        info = json.loads(r.stdout)
        return int(info["streams"][0]["width"]), int(info["streams"][0]["height"]), float(info["format"]["duration"])
    except (ValueError, KeyError, IndexError):
        return None


def render_piece(props, start, seconds, total, width, height, out_mov):
    """Render one transparent piece (ProRes 4444 with alpha) with the animated renderer's Overlay composition."""
    piece = {k: props[k] for k in ("visualTemplate", "templateText", "templateAccent", "introAnimation", "outroAnimation", "animationColor") if k in props}
    piece.update({"hookSeconds": 0, "seconds": seconds, "clockOffset": start, "clockTotal": total})
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8", dir=REMOTION) as f:
        json.dump(piece, f)
        pfile = f.name
    try:
        cmd = ["npx", "remotion", "render", "src/index.ts", "Overlay", out_mov, f"--props={pfile}", f"--width={width}", f"--height={height}",
               "--codec=prores", "--prores-profile=4444", "--pixel-format=yuva444p10le", "--image-format=png", "--muted"]
        r = subprocess.run(cmd, cwd=REMOTION, shell=(os.name == "nt"), capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(out_mov):
            raise RuntimeError((r.stderr or r.stdout or "overlay render failed")[-400:])
    finally:
        try:
            os.remove(pfile)
        except OSError:
            pass


def composite(video, pieces, out, codec="libx264", quality_params=None, ffmpeg="ffmpeg"):
    """Lay each (overlay file, start seconds) over `video`; returns True when `out` was written."""
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", video]
    for mov, _ in pieces:
        cmd += ["-i", mov]
    chain, cur = [], "0:v"
    for i, (_, start) in enumerate(pieces, start=1):
        chain.append(f"[{i}:v]format=yuva444p,setpts=PTS+{start:.3f}/TB[o{i}]")
        chain.append(f"[{cur}][o{i}]overlay=eof_action=pass:format=auto[v{i}]")
        cur = f"v{i}"
    cmd += ["-filter_complex", ";".join(chain), "-map", f"[{cur}]", "-map", "0:a?", "-c:a", "copy", "-c:v", codec,
            *(quality_params or ["-crf", "18", "-preset", "veryfast"]), "-pix_fmt", "yuv420p", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 1000


def _remove_work_folder(work):
    """Delete the temporary folder made by apply_to_video and nothing else: the files this module wrote in it, then the (now empty) folder.
    A folder that holds anything else is left alone."""
    try:
        for name in os.listdir(work):
            if name.startswith("piece_") and name.endswith(".mov") or name == "with_overlay.mp4":
                os.remove(os.path.join(work, name))
        os.rmdir(work)
    except OSError:
        pass


def apply_to_video(video, props, codec="libx264", quality_params=None, log=print):
    """Draw the chosen visual template / covers over `video` (in place). Returns True when something was applied."""
    if not wanted(props):
        return False
    info = probe(video)
    if not info:
        log("[Warning] Overlay skipped: the video could not be read.")
        return False
    width, height, total = info
    pieces = plan(total, props)
    if not pieces:
        return False
    work = tempfile.mkdtemp(prefix="overlay_", dir=os.path.dirname(os.path.abspath(video)))
    try:
        rendered = []
        for i, (start, seconds) in enumerate(pieces):
            mov = os.path.join(work, f"piece_{i}.mov")
            log(f"[Log] Rendering overlay piece {i + 1}/{len(pieces)} ({seconds:.1f}s at {start:.1f}s)...")
            render_piece(props, start, seconds, total, width, height, mov)
            rendered.append((mov, start))
        tmp_out = os.path.join(work, "with_overlay.mp4")
        if not composite(video, rendered, tmp_out, codec=codec, quality_params=quality_params):
            raise RuntimeError("FFmpeg could not lay the overlay over the video")
        os.replace(tmp_out, video)
        log("[Log] Template / covers applied to the highlights video.")
        return True
    except Exception as e:
        log(f"[Warning] Template / covers skipped for the highlights video ({e}); the video is unchanged.")
        return False
    finally:
        _remove_work_folder(work)
