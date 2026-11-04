import os
import re

from engine.remotion_renderer import clean_hook_text, overlay_props

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMOTION = os.path.join(ROOT, "remotion-video")


def _emoji_file_name(emoji):
    """Python twin of captionEmoji.ts::emojiFileName."""
    cps = [format(ord(c), "x") for c in emoji]
    if "200d" not in cps:
        cps = [c for c in cps if c != "fe0f"]
    return "-".join(cps)


def test_clean_hook_text_trims_and_limits():
    assert clean_hook_text("  He   never\nsaw it coming  ") == "He never saw it coming"
    long = "one two three four five six seven eight nine ten eleven"
    assert clean_hook_text(long) == "one two three four five six seven eight nine..."
    assert len(clean_hook_text("x" * 20 + " " + "y" * 80)) <= 63


def test_clean_hook_text_rejects_unusable_values():
    for bad in (None, "", "   ", 5, "keywords: pricing, plan"):
        assert clean_hook_text(bad) == ""


def test_overlay_props_hook_off_by_default(monkeypatch):
    monkeypatch.delenv("SHORTSFLOW_CAPTION_EMOJI", raising=False)
    props = overlay_props(None)
    assert props == {"captionEmoji": False}


def test_overlay_props_with_hook_and_emoji(monkeypatch):
    monkeypatch.setenv("SHORTSFLOW_CAPTION_EMOJI", "1")
    props = overlay_props("The secret nobody tells you", hook_seconds=3)
    assert props["captionEmoji"] is True
    assert props["hookText"] == "The secret nobody tells you"
    assert props["hookSeconds"] == 3.0


def test_every_keyword_emoji_has_a_bundled_image():
    src = open(os.path.join(REMOTION, "src", "captionEmoji.ts"), encoding="utf-8").read()
    table = src.split("EMOJI_BY_WORD: Record<string, string> = {", 1)[1].split("\n};", 1)[0]
    emojis = {m for m in re.findall(r'"([^"]+)"', table) if not re.fullmatch(r"[a-z_]*", m)}
    assert len(emojis) > 30
    missing = [e for e in emojis if not os.path.isfile(os.path.join(REMOTION, "public", "emoji", _emoji_file_name(e) + ".png"))]
    assert not missing, f"no bundled Twemoji image for {missing}"


def test_twemoji_license_is_bundled():
    assert os.path.isfile(os.path.join(REMOTION, "public", "emoji", "LICENSE-Twemoji.txt"))
