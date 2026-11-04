import os

import pytest

from engine import script_fonts as sf
from engine.reel_captions import _clean, ass_document

pytest.importorskip("fontTools")

ARABIC_FONT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "remotion-video", "public", "fonts", "NotoSansArabic.ttf")


def test_language_detection_from_the_characters():
    assert sf.cjk_language("こんにちは世界") == "ja"
    assert sf.cjk_language("안녕하세요") == "ko"
    assert sf.cjk_language("你好，世界") == "zh"
    assert sf.cjk_language("日本語", hint="ja") == "ja"   # Han only: the hint decides, default is Chinese
    assert sf.cjk_language("日本語") == "zh"
    assert sf.cjk_language("hello мир नमस्ते مرحبا") is None
    assert sf.has_arabic("مرحبا") and sf.has_rtl("שלום") and not sf.has_arabic("שלום")


def test_ensure_base_font_downloads_once_and_survives_offline(tmp_path):
    calls = []

    def fake(url, dest):
        calls.append(url)
        with open(dest, "wb") as f:
            f.write(b"0" * 1_500_000)

    path = sf.ensure_base_font("ja", download=fake, cache_dir=str(tmp_path))
    assert path and os.path.basename(path) == "NotoSansJP.ttf" and "notosansjp" in calls[0]
    assert sf.ensure_base_font("ja", download=fake, cache_dir=str(tmp_path)) == path and len(calls) == 1

    def offline(url, dest):
        raise OSError("no network")

    assert sf.ensure_base_font("ko", download=offline, cache_dir=str(tmp_path)) is None
    assert sf.cjk_subset("안녕하세요", download=offline, cache_dir=str(tmp_path)) is None
    assert sf.ensure_base_font("fr", cache_dir=str(tmp_path)) is None


def test_no_cjk_text_needs_no_font(tmp_path):
    assert sf.cjk_subset("plain english and русский", cache_dir=str(tmp_path)) is None


def test_subset_keeps_only_the_wanted_characters_and_names_the_family(tmp_path):
    from fontTools.ttLib import TTFont
    out = str(tmp_path / "arabic.ttf")
    sf.subset_font(ARABIC_FONT_FILE, out, {ord("م"), ord("ر"), ord(" "), ord("A")}, "SFTest-ar-00000000")
    font = TTFont(out)
    cmap = font.getBestCmap()
    assert ord("م") in cmap and ord("ر") in cmap and ord("ب") not in cmap
    assert font["name"].getDebugName(1) == "SFTest-ar-00000000"
    assert font["OS/2"].usWeightClass == 700
    assert os.path.getsize(out) < os.path.getsize(ARABIC_FONT_FILE) / 3


def test_cjk_subset_is_named_after_its_characters_and_reused(tmp_path):
    base_dir = tmp_path / "fonts"
    base_dir.mkdir()
    # the bundled Arabic font stands in for the 10 MB CJK download: it has no CJK glyphs but exercises the whole path
    with open(ARABIC_FONT_FILE, "rb") as f:
        data = f.read()
    (base_dir / "NotoSansSC.ttf").write_bytes(data + b"\0" * 1_000_000)  # > 1 MB so the cache check accepts it
    family, path = sf.cjk_subset("你好，世界", cache_dir=str(base_dir))
    assert family.startswith("SFCJK-zh-") and os.path.exists(path)
    assert sf.cjk_subset("你好，世界", cache_dir=str(base_dir)) == (family, path)
    other = sf.cjk_subset("再见", cache_dir=str(base_dir))
    assert other[0] != family
    assert sf.subset_files_for("Dialogue: ...{\\fn%s}你好" % family, os.path.dirname(path)) == [path]


def test_ass_words_get_the_right_font_override():
    assert _clean("مرحبا").startswith("{\\fnNoto Sans Arabic}")
    assert _clean("你好", "SFCJK-zh-12345678").startswith("{\\fnSFCJK-zh-12345678}")
    assert _clean("你好") == "你好"             # no subset available: unchanged (old behaviour)
    assert _clean("hello", "SFCJK-zh-12345678") == "HELLO"


def test_ass_document_names_the_cjk_font(monkeypatch):
    monkeypatch.setattr("engine.reel_captions.cjk_subset", lambda text: ("SFCJK-ja-aaaaaaaa", "x.ttf"))
    doc = ass_document([(0.0, 1.0, "こんにちは"), (1.0, 2.0, "hello")])
    assert "{\\fnSFCJK-ja-aaaaaaaa}こんにちは" in doc and ",,HELLO\n" in doc
