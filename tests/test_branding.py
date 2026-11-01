import json
import subprocess

import imageio_ffmpeg
import pytest
from PIL import Image

from engine import branding


@pytest.fixture
def logo(tmp_path):
    p = tmp_path / "logo.png"
    Image.new("RGBA", (200, 80), (255, 0, 80, 255)).save(p)
    return str(p)


def test_load_brand_merges_preset_and_cli(tmp_path, logo):
    preset = tmp_path / "brand.json"
    preset.write_text(json.dumps({"logo": "logo.png", "handle": "@old", "logo_position": "bottom-left", "bogus": 1}))
    brand = branding.load_brand(str(preset), handle="@new")
    assert brand["handle"] == "@new" and brand["logo_position"] == "bottom-left"
    assert brand["logo"] == str(tmp_path / "logo.png") and "bogus" not in brand


def test_load_brand_nothing_and_errors(tmp_path):
    assert branding.load_brand() is None
    with pytest.raises(FileNotFoundError):
        branding.load_brand(logo=str(tmp_path / "missing.png"))
    bad = tmp_path / "b.json"
    bad.write_text(json.dumps({"handle": "@x", "logo_position": "middle"}))
    with pytest.raises(ValueError):
        branding.load_brand(str(bad))


def test_watermark_is_placed_in_the_requested_corner(logo):
    brand = branding.load_brand(logo=logo)  # top-right by default
    layer = branding.render_watermark(brand, 540, 960)
    assert layer.size == (540, 960)
    box = layer.getchannel("A").getbbox()
    assert box and box[0] > 540 // 2 and box[3] < 960 // 4
    brand["logo_position"] = "bottom-left"
    box = branding.render_watermark(brand, 540, 960).getchannel("A").getbbox()
    assert box[2] < 540 // 2 and box[1] > 960 // 2


def test_end_card_only_when_text_given(logo):
    assert branding.render_end_card(branding.load_brand(logo=logo), 540, 960) is None
    card = branding.render_end_card(branding.load_brand(logo=logo, end_card="Follow for more"), 540, 960)
    assert card.size == (540, 960) and card.getpixel((5, 5))[3] == 255


def test_apply_brand_keeps_size_and_duration(tmp_path, logo):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    src = tmp_path / "in.mp4"
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=blue:s=270x480:d=3:r=15", "-f", "lavfi",
                    "-i", "sine=d=3", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src)],
                   capture_output=True, check=True)
    brand = branding.load_brand(logo=logo, handle="@acme", end_card="Follow")
    out = branding.apply_brand(str(src), brand, str(tmp_path / "out.mp4"), ffmpeg)
    w, h, d = branding._probe(out, ffmpeg)
    assert (w, h) == (270, 480) and abs(d - 3.0) < 0.3
