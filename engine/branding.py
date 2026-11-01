"""Brand kit: logo watermark, @handle badge and an end card burned into finished clips.

The overlays are drawn with Pillow into PNGs and composited by FFmpeg, so no FFmpeg font setup is needed.

    python -m engine.branding clip.mp4 --logo logo.png --handle @mychannel --end_card "Follow for more"
    python main.py --source_video URL --brand brand.json        # same options as a preset file

brand.json: {"logo": "logo.png", "logo_position": "top-right", "logo_opacity": 0.85, "handle": "@mychannel",
             "end_card": "Follow for more", "end_card_seconds": 2.0, "color": "#FFEA00"}
"""
import argparse
import json
import os
import subprocess
import tempfile

POSITIONS = ("top-left", "top-right", "bottom-left", "bottom-right")
DEFAULTS = {"logo": None, "logo_position": "top-right", "logo_opacity": 0.85, "logo_width": 0.18,
            "handle": None, "end_card": None, "end_card_seconds": 2.0, "color": "#FFEA00"}


def load_brand(path=None, logo=None, handle=None, end_card=None):
    """Merge a brand.json preset with explicit CLI values (CLI wins). Returns None if nothing to apply."""
    brand = dict(DEFAULTS)
    if path:
        with open(path, encoding="utf-8") as f:
            brand.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
        base = os.path.dirname(os.path.abspath(path))
        if brand["logo"] and not os.path.isabs(brand["logo"]):
            brand["logo"] = os.path.join(base, brand["logo"])
    for key, value in (("logo", logo), ("handle", handle), ("end_card", end_card)):
        if value:
            brand[key] = value
    if brand["logo_position"] not in POSITIONS:
        raise ValueError(f"logo_position must be one of {', '.join(POSITIONS)}")
    if brand["logo"] and not os.path.isfile(brand["logo"]):
        raise FileNotFoundError(f"Brand logo not found: {brand['logo']}")
    return brand if (brand["logo"] or brand["handle"] or brand["end_card"]) else None


def _font(size):
    from PIL import ImageFont
    for name in ("arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _hex(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def render_watermark(brand, width, height):
    """Transparent full-frame PNG with the logo and handle, or None."""
    from PIL import Image, ImageDraw
    if not (brand["logo"] or brand["handle"]):
        return None
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    margin = int(width * 0.04)
    top = brand["logo_position"].startswith("top")
    left = brand["logo_position"].endswith("left")
    # keep clear of the platform UI: top ~8 % and bottom ~18 % are covered by Shorts/Reels chrome
    y_top, y_bottom = int(height * 0.08), int(height * 0.82)
    y = y_top if top else y_bottom
    x_edge = margin if left else width - margin
    if brand["logo"]:
        logo = Image.open(brand["logo"]).convert("RGBA")
        lw = int(width * brand["logo_width"])
        logo = logo.resize((lw, max(1, int(logo.height * lw / logo.width))))
        alpha = logo.getchannel("A").point(lambda a: int(a * brand["logo_opacity"]))
        logo.putalpha(alpha)
        layer.alpha_composite(logo, (x_edge if left else x_edge - lw, y if top else y - logo.height))
        y = y + logo.height + 12 if top else y - logo.height - 12
    if brand["handle"]:
        draw = ImageDraw.Draw(layer)
        font = _font(max(24, int(width * 0.04)))
        box = draw.textbbox((0, 0), brand["handle"], font=font)
        tw, th = box[2] - box[0], box[3] - box[1]
        px = x_edge if left else x_edge - tw
        py = y if top else y - th
        draw.text((px - box[0] + 2, py - box[1] + 2), brand["handle"], font=font, fill=(0, 0, 0, 160))
        draw.text((px - box[0], py - box[1]), brand["handle"], font=font, fill=(255, 255, 255, int(255 * brand["logo_opacity"])))
    return layer


def render_end_card(brand, width, height):
    """Opaque-ish full-frame end card PNG, or None."""
    from PIL import Image, ImageDraw
    if not brand["end_card"]:
        return None
    card = Image.new("RGBA", (width, height), (8, 10, 16, 255))
    draw = ImageDraw.Draw(card)
    color = _hex(brand["color"])
    y = int(height * 0.42)
    if brand["logo"]:
        logo = Image.open(brand["logo"]).convert("RGBA")
        lw = int(width * 0.34)
        logo = logo.resize((lw, max(1, int(logo.height * lw / logo.width))))
        card.alpha_composite(logo, ((width - lw) // 2, int(height * 0.26)))
        y = int(height * 0.26) + logo.height + 40
    font = _font(max(36, int(width * 0.075)))
    words, lines, line = brand["end_card"].split(), [], ""
    for word in words:  # wrap to 85 % of the width
        trial = f"{line} {word}".strip()
        if draw.textbbox((0, 0), trial, font=font)[2] > width * 0.85 and line:
            lines.append(line)
            line = word
        else:
            line = trial
    lines.append(line)
    for text in lines:
        box = draw.textbbox((0, 0), text, font=font)
        draw.text(((width - (box[2] - box[0])) // 2 - box[0], y - box[1]), text, font=font, fill=color)
        y += (box[3] - box[1]) + 24
    if brand["handle"]:
        small = _font(max(28, int(width * 0.05)))
        box = draw.textbbox((0, 0), brand["handle"], font=small)
        draw.text(((width - (box[2] - box[0])) // 2 - box[0], y + 20 - box[1]), brand["handle"], font=small, fill=(255, 255, 255))
    return card


def _probe(video_path, ffmpeg_exe):
    """(width, height, duration) from ffmpeg's banner so no ffprobe binary is needed."""
    import re
    err = subprocess.run([ffmpeg_exe, "-i", video_path], capture_output=True, text=True).stderr
    size = re.search(r"Video:.*?,\s*(\d{2,5})x(\d{2,5})", err)
    dur = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", err)
    if not size or not dur:
        raise RuntimeError(f"Could not read video info for {video_path}")
    h, m, s = dur.groups()
    return int(size.group(1)), int(size.group(2)), int(h) * 3600 + int(m) * 60 + float(s)


def apply_brand(video_path, brand, output_path=None, ffmpeg_exe=None):
    """Burn the brand kit into `video_path` (replaced in place unless output_path is given). Returns the path."""
    if ffmpeg_exe is None:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    width, height, duration = _probe(video_path, ffmpeg_exe)
    watermark = render_watermark(brand, width, height)
    card = render_end_card(brand, width, height)
    card_start = max(0.0, duration - float(brand["end_card_seconds"]))

    with tempfile.TemporaryDirectory() as tmp:
        cmd, chain, last, n = [ffmpeg_exe, "-y", "-i", video_path], [], "0:v", 1
        if watermark is not None:
            wm_path = os.path.join(tmp, "wm.png")
            watermark.save(wm_path)
            cmd += ["-i", wm_path]
            chain.append(f"[{last}][{n}:v]overlay=0:0[v{n}]")
            last, n = f"v{n}", n + 1
        if card is not None:
            card_path = os.path.join(tmp, "card.png")
            card.save(card_path)
            cmd += ["-i", card_path]
            chain.append(f"[{last}][{n}:v]overlay=0:0:enable='gte(t,{card_start:.2f})'[v{n}]")
            last, n = f"v{n}", n + 1
        out = output_path or video_path + ".branded.mp4"
        cmd += ["-filter_complex", ";".join(chain), "-map", f"[{last}]", "-map", "0:a?", "-c:v", "libx264",
                "-preset", "fast", "-crf", "18", "-c:a", "copy", "-movflags", "+faststart", out]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0 or not os.path.exists(out):
            raise RuntimeError("FFmpeg branding failed: " + res.stderr[-400:])
    if output_path is None:
        os.replace(out, video_path)
        return video_path
    return output_path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Burn a logo watermark, @handle and end card into a video")
    ap.add_argument("video")
    ap.add_argument("--brand", help="brand.json preset")
    ap.add_argument("--logo")
    ap.add_argument("--handle")
    ap.add_argument("--end_card", help="end card text shown for the last seconds")
    ap.add_argument("--output", help="write here instead of replacing the input")
    a = ap.parse_args(argv)
    brand = load_brand(a.brand, a.logo, a.handle, a.end_card)
    if not brand:
        raise SystemExit("Nothing to apply: pass --logo, --handle, --end_card or --brand brand.json")
    print(apply_brand(a.video, brand, a.output))


if __name__ == "__main__":
    main()
