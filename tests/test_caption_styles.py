import json
import os
import re
import sys

import pytest

from engine import remotion_renderer as rr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def _quoted(text):
    return re.findall(r'"([A-Z_]+)"', text)


def test_new_styles_exist_and_auto_only_picks_the_original_four():
    assert rr.CAPTION_STYLES[:4] == ["HORMOZI", "GLOW_BOX", "BOUNCE", "MINIMAL"]
    assert {"KARAOKE", "NEON", "BAR"} <= set(rr.CAPTION_STYLES)
    # AUTO / RANDOM must not start picking the opt-in styles (the daily channel relies on the old pool)
    assert rr.AUTO_CAPTION_STYLES == ["HORMOZI", "GLOW_BOX", "BOUNCE", "MINIMAL"]


def test_every_surface_lists_the_same_styles():
    expected = set(rr.CAPTION_STYLES)
    tsx = _read("remotion-video", "src", "ShortFlow.tsx")
    assert set(_quoted(re.search(r"captionStyle: z\.enum\(\[(.*?)\]\)", tsx).group(1))) == expected
    main = _read("shortsflow", "_main.py")
    assert set(_quoted(re.search(r'"--caption_style".*?choices=\[(.*?)\]', main).group(1))) - {"AUTO", "RANDOM"} == expected
    api = _read("shortsflow", "api", "app.py")
    assert set(_quoted(re.search(r"CaptionStyle = Literal\[(.*?)\]", api).group(1))) - {"AUTO", "RANDOM"} == expected
    rerender = _read("engine", "rerender.py")
    assert set(_quoted(re.search(r'"--style", choices=\[(.*?)\]', rerender).group(1))) == expected
    web = _read("webui.py")
    assert set(_quoted(re.search(r"^CAPTION_STYLES = \[(.*?)\]", web, re.M).group(1))) - {"AUTO", "RANDOM"} == expected
    assert set(re.findall(r'\("[^"]+", "([A-Z_]+)"\)', re.search(r"CAPTION_CHOICES = \[(.*?)\]\n", web, re.S).group(1))) == expected


def test_every_style_has_a_preview_image_for_the_browser_app():
    for style in rr.CAPTION_STYLES:
        path = os.path.join(ROOT, "assets", "caption_previews", f"{style}.jpg")
        assert os.path.isfile(path) and os.path.getsize(path) > 2000, style


@pytest.mark.parametrize("raw,expected", [
    ("#ff3366", "#FF3366"), ("FF3366", "#FF3366"), ("  #fe0 ", "#FFEE00"), ("#abc", "#AABBCC"),
])
def test_caption_color_is_normalised(raw, expected):
    assert rr.normalize_caption_color(raw) == expected


@pytest.mark.parametrize("bad", [None, "", "red", "#12", "#12345", "#1234567", "#gggggg", 7])
def test_caption_color_rejects_non_hex(bad):
    assert rr.normalize_caption_color(bad) is None


def test_caption_color_prop_only_when_valid(monkeypatch):
    monkeypatch.delenv("SHORTSFLOW_CAPTION_EMOJI", raising=False)
    monkeypatch.delenv("SHORTSFLOW_CAPTION_COLOR", raising=False)
    assert rr.overlay_props(None) == {"captionEmoji": False}          # default render is unchanged
    monkeypatch.setenv("SHORTSFLOW_CAPTION_COLOR", "#ff3366")
    assert rr.overlay_props(None)["captionColor"] == "#FF3366"
    monkeypatch.setenv("SHORTSFLOW_CAPTION_COLOR", "nonsense")
    assert "captionColor" not in rr.overlay_props(None)


def test_schema_validates_the_colour_as_hex():
    tsx = _read("remotion-video", "src", "ShortFlow.tsx")
    assert "captionColor: z.string().regex(/^#[0-9a-fA-F]{6}$/).optional()" in tsx


def test_line_styles_skip_letter_spacing_for_joined_and_cjk_scripts():
    """The TSX helper must cover Arabic/Hebrew (via isRtl), CJK and Devanagari: spacing breaks their joins / ligatures."""
    tsx = _read("remotion-video", "src", "ShortFlow.tsx")
    m = re.search(r"const NO_SPACING_RE = /\[(.*?)\]/;", tsx)
    assert m, "NO_SPACING_RE missing"
    cls = m.group(1)
    py = re.compile("[" + cls.encode().decode("unicode_escape") + "]")
    for ch in ("あ", "ア", "中", "한", "ह"):
        assert py.search(ch), ch
    for ch in ("a", "Ж", "Ω", "ع"):                                             # Latin / Cyrillic / Greek; Arabic goes through isRtl
        assert not py.search(ch), ch
    assert "const noLetterSpacing = (s: string) => isRtl(s) || NO_SPACING_RE.test(s);" in tsx


def test_rerender_keeps_the_caption_colour_of_the_original_run(tmp_path, monkeypatch):
    from engine import rerender
    from test_rerender import _fake_engine, _session

    session = _session(tmp_path)
    data = json.loads((session / "results.json").read_text())
    data["settings"].update({"caption_color": "#FF3366", "caption_style": "NEON"})
    (session / "results.json").write_text(json.dumps(data))
    calls = {}
    _fake_engine(monkeypatch, calls)

    def extract_with_env(source, highlights, transcript, out_dir, **kw):
        calls["color_env"] = os.environ.get("SHORTSFLOW_CAPTION_COLOR")
        calls["style"] = kw.get("caption_style")
        path = os.path.join(out_dir, "video_clip_1.mp4")
        with open(path, "wb") as f:
            f.write(b"new video")
        return [path]
    sys.modules["engine.video_gen"].extract_segments = extract_with_env
    monkeypatch.delenv("SHORTSFLOW_CAPTION_COLOR", raising=False)
    monkeypatch.chdir(tmp_path)

    rerender.rerender_clip(str(session), 1, start=6.0, end=12.0)
    assert calls["color_env"] == "#FF3366" and calls["style"] == "NEON"
    assert "SHORTSFLOW_CAPTION_COLOR" not in os.environ               # does not leak into later in-process renders
