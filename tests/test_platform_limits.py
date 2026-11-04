import pytest

from engine import platform_limits as pl
from engine import publish


def test_truncate_words_cuts_at_a_word_and_respects_the_limit():
    text = "Prices doubled last year in Berlin and nobody saw it coming"
    for limit in (10, 20, 33, 40):
        out = pl.truncate_words(text, limit)
        assert len(out) <= limit
        assert out.endswith("…")
        assert text.startswith(out[:-1].rstrip())
        body = out[:-1]
        assert not body or text[len(body)] == " "          # never inside a word
    assert pl.truncate_words(text, 500) == text
    assert pl.truncate_words("", 10) == ""
    assert pl.truncate_words("abc", 0) == ""


def test_truncate_words_single_long_word():
    out = pl.truncate_words("Supercalifragilisticexpialidocious", 12)
    assert len(out) <= 12 and out.endswith("…")


def test_clean_hashtags():
    assert pl.clean_hashtags(["AI tools", "ai tools", "#shorts", "!!", "a_b"]) == ["#AItools", "#shorts", "#a_b"]
    assert len(pl.clean_hashtags([f"t{i}" for i in range(50)], limit=30)) == 30


def test_join_caption_keeps_hashtags_whole():
    tags = "#economy #prices"
    assert pl.join_caption("Why prices doubled", tags, 100) == "Why prices doubled #economy #prices"
    long_title = "word " * 100
    out = pl.join_caption(long_title, tags, 60)
    assert len(out) <= 60 and out.endswith("#economy #prices")
    assert pl.join_caption("T", "#x" * 40, 20) == "T"           # hashtags alone do not fit: title only


def test_fit_tag_list_counts_the_whole_list():
    tags = ["alpha", "beta gamma", "delta"]
    assert pl.fit_tag_list(tags, 500) == tags
    kept = pl.fit_tag_list(tags, 12)
    assert kept == ["alpha"]
    assert pl.fit_tag_list(["#x", "", "y"], 50) == ["x", "y"]


def test_fit_for_platform_tiktok_and_instagram_caption_limits():
    desc = "A hook line.\n\n" + "More detail here. " * 300 + "\n#econ #prices"
    tags = [f"tag{i}" for i in range(40)]
    tt = pl.fit_for_platform("tiktok", "Why prices doubled", desc, tags)
    ig = pl.fit_for_platform("instagram", "Why prices doubled", desc, tags)
    assert len(tt["text"]) <= 2200 and len(ig["text"]) <= 2200
    assert len(tt["hashtags"]) <= 5 and len(ig["hashtags"]) <= 30
    assert tt["text"].startswith("Why prices doubled")
    assert tt["text"].endswith(" ".join(tt["hashtags"]))
    assert "#econ" in tt["hashtags"] and "#prices" in tt["hashtags"]       # the description's own hashtags come first
    assert "#econ" not in tt["text"].split("\n\n")[1] if len(tt["text"].split("\n\n")) > 2 else True


def test_fit_for_platform_youtube_limits():
    title = "T " * 80
    desc = "line " * 2000 + "#shorts"
    tags = ["word%d" % i for i in range(200)]
    yt = pl.fit_for_platform("youtube", title, desc, tags)
    assert len(yt["title"]) <= 100 and len(yt["text"]) <= 5000
    assert len(",".join(yt["tags"])) <= 500
    assert len(yt["hashtags"]) <= 15
    assert yt["text"].endswith(" ".join(yt["hashtags"]))
    assert pl.fit_for_platform("shorts", "T", "d")["platform"] == "youtube"


def test_fit_for_platform_short_input_is_untouched():
    out = pl.fit_for_platform("tiktok", "Why prices doubled", "Short and sweet.", ["economy"])
    assert out["text"] == "Why prices doubled\n\nShort and sweet.\n\n#economy"


def test_fit_for_platform_huge_title_drops_hashtags_whole_not_halves():
    out = pl.fit_for_platform("tiktok", "x " * 2000, "", ["alpha", "beta"])
    assert len(out["text"]) <= 2200
    assert all(h in ("#alpha", "#beta") for h in out["text"].split() if h.startswith("#"))


def test_unknown_platform():
    with pytest.raises(ValueError):
        pl.fit_for_platform("myspace", "t")


def test_publish_fields_use_word_boundary_truncation():
    item = {"title": "word " * 600, "tags": ["economy", "prices"], "description": "d"}
    f = dict(publish.build_fields(item, ["tiktok", "youtube"], "u"))
    assert len(f["tiktok_title"]) <= 2200 and f["tiktok_title"].endswith("#economy #prices")
    assert len(f["youtube_title"]) <= 100 and f["youtube_title"].endswith("…")
    short = dict(publish.build_fields({"title": "Why prices doubled", "tags": ["economy", "prices"]}, ["tiktok"], "u"))
    assert short["tiktok_title"] == "Why prices doubled #economy #prices"
