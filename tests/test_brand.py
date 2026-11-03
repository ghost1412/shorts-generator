import json
import os

import pytest
from PIL import Image

from shortsflow import brand


def _logo(path, size=(2000, 800), color=(255, 0, 0, 120)):
    Image.new("RGBA", size, color).save(path)
    return str(path)


def test_nothing_saved_means_no_arguments(tmp_path):
    assert brand.load(str(tmp_path)) == {}
    assert brand.cli_args(str(tmp_path)) == []


def test_save_validates_normalises_and_resizes_the_logo(tmp_path):
    home = str(tmp_path)
    msg = brand.save(home, logo_path=_logo(tmp_path / "big.png"), handle=" @My.Channel ", end_card="Follow for more", color="#00ff88",
                     position="bottom-left")
    assert "logo" in msg and "@My.Channel" in msg
    saved = brand.load(home)
    assert saved["handle"] == "@My.Channel" and saved["end_card"] == "Follow for more" and saved["color"] == "#00ff88"
    assert saved["logo_position"] == "bottom-left" and os.path.exists(saved["logo"])
    with Image.open(saved["logo"]) as im:
        assert max(im.size) == brand.MAX_LOGO_SIDE and im.mode == "RGBA"       # shrunk, transparency kept
    assert brand.cli_args(home) == ["--brand", os.path.join(home, "brand", "brand.json")]
    data = json.loads((tmp_path / "brand" / "brand.json").read_text())
    assert data["logo"] == "logo.png"                                           # relative, the engine resolves it next to the json


def test_logo_is_kept_when_only_the_text_changes(tmp_path):
    home = str(tmp_path)
    brand.save(home, logo_path=_logo(tmp_path / "l.png", (100, 100)), handle="a")
    brand.save(home, handle="b", end_card="")
    assert brand.load(home)["handle"] == "@b" and brand.load(home)["logo"]


@pytest.mark.parametrize("kwargs,reason", [
    ({"handle": "bad handle!"}, "handle"),
    ({"handle": "ok", "end_card": "x" * 61}, "too long"),
    ({"handle": "ok", "color": "yellow"}, "colour"),
    ({"handle": "ok", "position": "middle"}, "position"),
    ({}, "at least"),
])
def test_bad_input_gets_a_plain_reason(tmp_path, kwargs, reason):
    with pytest.raises(ValueError, match=reason):
        brand.save(str(tmp_path), **kwargs)
    assert brand.load(str(tmp_path)) == {}


def test_unreadable_logo_is_rejected_and_clear_removes_everything(tmp_path):
    home = str(tmp_path)
    bad = tmp_path / "notimage.png"
    bad.write_text("nope")
    with pytest.raises(ValueError, match="image"):
        brand.save(home, logo_path=str(bad), handle="a")
    brand.save(home, logo_path=_logo(tmp_path / "ok.png", (50, 50)), handle="a")
    brand.clear(home)
    assert brand.load(home) == {} and brand.cli_args(home) == []


def test_the_engine_accepts_what_this_module_writes(tmp_path):
    from engine.branding import load_brand
    home = str(tmp_path)
    brand.save(home, logo_path=_logo(tmp_path / "l.png", (64, 64)), handle="chan", end_card="Follow", color="#112233")
    engine_view = load_brand(path=os.path.join(home, "brand", "brand.json"))
    assert engine_view["handle"] == "@chan" and engine_view["end_card"] == "Follow" and engine_view["color"] == "#112233"
    assert os.path.isfile(engine_view["logo"])
