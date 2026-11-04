"""Render one preview still per caption style with Remotion -> assets/caption_previews/<STYLE>.jpg (shown in the browser app).

Needs Node + `npm ci` in remotion-video. Re-run after changing caption styling:

    python scripts/make_caption_previews.py            # all styles
    python scripts/make_caption_previews.py NEON BAR   # only these
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMOTION = os.path.join(ROOT, "remotion-video")
OUT = os.path.join(ROOT, "assets", "caption_previews")
STYLES = ["HORMOZI", "GLOW_BOX", "BOUNCE", "MINIMAL", "KARAOKE", "NEON", "BAR"]
BG_NAME = "_preview_bg.jpg"
WORDS = [("Nobody", 0.1, 0.6), ("tells", 0.6, 1.0), ("you", 1.0, 1.3), ("this", 1.3, 1.8), ("about", 1.8, 2.3), ("light", 2.3, 3.0)]


def make_backdrop(path, w=1080, h=1920):
    """A soft sunset gradient (generated here, so there is nothing to license)."""
    from PIL import Image, ImageDraw, ImageFilter
    img = Image.new("RGB", (w, h))
    px = ImageDraw.Draw(img)
    top, mid, bottom = (38, 50, 110), (196, 98, 112), (255, 176, 96)
    for y in range(h):
        t = y / (h - 1)
        a, b, k = (top, mid, t / 0.55) if t < 0.55 else (mid, bottom, (t - 0.55) / 0.45)
        px.line([(0, y), (w, y)], fill=tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3)))
    glow = Image.new("RGB", (w, h), (0, 0, 0))
    ImageDraw.Draw(glow).ellipse([w * 0.2, h * 0.52, w * 0.8, h * 0.72], fill=(255, 214, 140))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    from PIL import ImageChops
    ImageChops.add(img, glow).save(path, quality=88)


def main():
    from PIL import Image
    os.makedirs(OUT, exist_ok=True)
    bg = os.path.join(REMOTION, "public", BG_NAME)
    make_backdrop(bg)
    try:
        for style in (sys.argv[1:] or STYLES):
            props = {"captionStyle": style, "titleText": "", "mode": "FACTS",
                     "words": [{"word": w, "start": s, "end": e} for w, s, e in WORDS],
                     "backgrounds": [{"path": BG_NAME, "start": 0, "end": 3, "type": "image"}]}
            with tempfile.TemporaryDirectory() as tmp:
                props_file = os.path.join(tmp, "props.json")
                png = os.path.join(tmp, "still.png")
                with open(props_file, "w", encoding="utf-8") as f:
                    json.dump(props, f)
                cmd = ["npx", "remotion", "still", "ShortFlow", png, f"--props={props_file}", "--frame=45", "--scale=0.4"]
                r = subprocess.run(cmd, cwd=REMOTION, shell=(sys.platform == "win32"), capture_output=True, text=True)
                if r.returncode != 0 or not os.path.exists(png):
                    raise SystemExit(f"remotion still failed for {style}:\n{r.stdout[-800:]}\n{r.stderr[-800:]}")
                Image.open(png).convert("RGB").save(os.path.join(OUT, f"{style}.jpg"), quality=82, optimize=True)
            print("wrote", f"{style}.jpg")
    finally:
        if os.path.exists(bg):
            os.remove(bg)


if __name__ == "__main__":
    main()
