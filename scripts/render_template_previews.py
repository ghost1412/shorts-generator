"""Render one preview still per visual template (docs/templates/<name>.jpg), on a public-domain sample frame with made-up sample text.

    python scripts/render_template_previews.py            # all templates
    python scripts/render_template_previews.py neon-frame  # one
    python scripts/render_template_previews.py --animations [tiles ...]   # short intro+outro clips of the transitions

A still is a single frame, so this is light enough to run locally. Needs Node and the remotion-video dependencies (npm install there).
"""
import json
import os
import subprocess
import sys
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMOTION = os.path.join(ROOT, "remotion-video")
OUT = os.path.join(ROOT, "docs", "templates")
FRAME = os.path.join(ROOT, "demos", "template_preview_frame.jpg")      # NASA Apollo 17 photo, public domain (Wikimedia Commons)

SAMPLE_TEXT = {
    "show": "The Sample Show", "speaker": "Alex Morgan", "role": "Host", "handle": "@sampleshow",
    "headline": "A sample headline goes here", "label": "LATEST", "cta": "Follow @sampleshow for more",
}
TEXT_OVERRIDE = {"episode-badge": {"label": "EP 12"}}      # the label slot means "EP 12" here, "LATEST" on the news banner
WORDS = [("Here", 0.2), ("is", 0.5), ("how", 0.8), ("a", 1.1), ("template", 1.4), ("looks", 1.9), ("on", 2.3), ("your", 2.6), ("clip", 3.0),
         ("with", 3.6), ("captions", 4.0), ("on", 4.6), ("top", 4.9), ("of", 5.3), ("it", 5.5), ("all", 6.0), ("the", 6.3), ("way", 6.6)]


def silent_wav(path, seconds=9):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000 * seconds)


def _props(**extra):
    props = {
        "audioUrl": "temp_assets/template_preview.wav", "mode": "FACTS", "titleText": None, "subtitleYPos": 1250, "captionStyle": "HORMOZI",
        "hookText": "This is the hook line", "hookSeconds": 2.8,
        "words": [{"word": w, "start": s, "end": s + 0.28} for w, s in WORDS],
        "backgrounds": [{"path": "temp_assets/template_preview.jpg", "start": 0, "end": 9, "type": "image", "orientation": "landscape"}],
    }
    props.update(extra)
    return props


def _prepare():
    assets = os.path.join(REMOTION, "public", "temp_assets")
    os.makedirs(assets, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    silent_wav(os.path.join(assets, "template_preview.wav"))
    with open(FRAME, "rb") as src, open(os.path.join(assets, "template_preview.jpg"), "wb") as dst:
        dst.write(src.read())
    return assets


def _run(cmd, label):
    r = subprocess.run(cmd, cwd=REMOTION, shell=(os.name == "nt"), capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-1500:], r.stderr[-1500:])
        raise SystemExit(f"{label} failed")


def animations(names):
    """One short clip per transition (docs/templates/anim-<name>.mp4): the intro (first second) then the outro (last second), 432x768."""
    sys.path.insert(0, ROOT)
    from engine.auto_edit import ANIMATION_NAMES
    names = names or list(ANIMATION_NAMES)
    assets = _prepare()
    ffmpeg = os.environ.get("FFMPEG_BINARY") or "ffmpeg"
    for name in names:
        parts = []
        for tag, frames, extra in (("intro", "0-29", {"introAnimation": name}), ("outro", "240-269", {"outroAnimation": name})):
            pfile = os.path.join(assets, f"anim_props_{name}_{tag}.json")
            with open(pfile, "w", encoding="utf-8") as f:
                json.dump(_props(animationColor="#6D28D9", **extra), f)
            part = os.path.join(assets, f"anim_{name}_{tag}.mp4")
            print(f"[Log] Rendering {name} {tag}")
            _run(["npx", "remotion", "render", "src/index.ts", "ShortFlow", part, f"--props={pfile}", f"--frames={frames}", "--scale=0.4",
                  "--crf=30", "--muted"], f"{name} {tag}")
            os.remove(pfile)
            parts.append(part)
        listing = os.path.join(assets, f"anim_{name}.txt")
        with open(listing, "w", encoding="utf-8") as f:
            f.write("".join("file '" + os.path.basename(p_) + "'" + chr(10) for p_ in parts))
        out = os.path.join(OUT, f"anim-{name}.mp4")
        r = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listing, "-an", "-c:v", "libx264", "-crf", "30",
                            "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], capture_output=True, text=True)
        for p_ in parts + [listing]:
            os.remove(p_)
        if r.returncode != 0:
            raise SystemExit(f"joining {name} failed: {r.stderr[-800:]}")
    print("[Log] Done:", OUT)


def main(names):
    sys.path.insert(0, ROOT)
    from engine.auto_edit import VISUAL_TEMPLATE_NAMES
    names = names or list(VISUAL_TEMPLATE_NAMES)
    assets = _prepare()
    for name in names:
        props = _props(visualTemplate=name, templateText={**SAMPLE_TEXT, **TEXT_OVERRIDE.get(name, {})})
        pfile = os.path.join(assets, f"preview_props_{name}.json")
        with open(pfile, "w", encoding="utf-8") as f:
            json.dump(props, f)
        out = os.path.join(OUT, f"{name}.jpg")
        print("[Log] Rendering preview:", name)
        _run(["npx", "remotion", "still", "src/index.ts", "ShortFlow", out, f"--props={pfile}", "--frame=75", "--scale=0.5",
              "--image-format=jpeg", "--jpeg-quality=82"], f"preview for {name}")
        os.remove(pfile)
    print("[Log] Done:", OUT)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--animations"]:
        animations(sys.argv[2:])
    else:
        main(sys.argv[1:])
