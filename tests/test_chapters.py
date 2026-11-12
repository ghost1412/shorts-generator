import json
import os

from engine import chapters as ch


def hl(*spans):
    return [{"start": s, "end": e} for s, e in spans]


# five 20 s segments from different parts of a source video
HIGHLIGHTS = hl((100, 120), (300, 320), (500, 520), (700, 720), (900, 920))
SEGMENTS = [
    {"start": 101, "end": 118, "text": "Pricing is the first thing people ask about, pricing tiers and pricing pages."},
    {"start": 301, "end": 318, "text": "Hiring took us three months and hiring was hard."},
    {"start": 501, "end": 518, "text": "Our onboarding flow cut churn by 20 percent."},
    {"start": 701, "end": 718, "text": "Maria explains the roadmap for next year."},
    {"start": 901, "end": 918, "text": "Final advice: ship early, ship often."},
]


def test_timeline_accounts_for_crossfades():
    spans = ch.reel_timeline(HIGHLIGHTS, xf=0.25)
    assert spans[0] == (0.0, 20.0)
    assert spans[1][0] == 19.75 and spans[2][0] == 39.5
    assert round(spans[-1][1], 2) == 99.0         # 5 * 20 - 4 * 0.25


def test_build_chapters_one_per_segment_and_starts_at_zero():
    chapters = ch.build_chapters(HIGHLIGHTS)
    assert len(chapters) == 5 and chapters[0]["start"] == 0.0
    assert all(c["end"] - c["start"] >= ch.MIN_CHAPTER for c in chapters)
    assert [c["segments"] for c in chapters] == [[0], [1], [2], [3], [4]]


def test_short_segments_are_merged_so_every_chapter_is_long_enough():
    chapters = ch.build_chapters(hl((0, 6), (10, 16), (20, 26), (30, 36), (40, 46), (50, 56), (60, 66), (70, 76)))
    assert len(chapters) >= 3
    assert chapters[0]["start"] == 0.0
    for a, b in zip(chapters, chapters[1:]):
        assert b["start"] >= a["start"]
    assert all(c["end"] - c["start"] >= ch.MIN_CHAPTER - 1e-6 for c in chapters)
    covered = sorted(i for c in chapters for i in c["segments"])
    assert covered == list(range(8))


def test_too_short_for_three_chapters_gives_none():
    assert ch.build_chapters(hl((0, 12), (20, 30))) == []             # two segments
    assert ch.build_chapters(hl((0, 8), (10, 18), (20, 28))) == []    # 24 s total: merging leaves fewer than three
    assert ch.build_chapters([]) == []


def test_max_chapters_is_respected():
    many = hl(*[(i * 100, i * 100 + 15) for i in range(30)])
    chapters = ch.build_chapters(many)
    assert len(chapters) <= ch.MAX_CHAPTERS
    assert chapters[0]["start"] == 0.0 and sorted(i for c in chapters for i in c["segments"]) == list(range(30))


def test_timeline_scales_to_the_real_reel_length():
    chapters = ch.build_chapters(HIGHLIGHTS, total=90.0)       # nominal 99 s, the file is 90 s
    assert round(chapters[-1]["end"], 2) == 90.0
    assert chapters[0]["start"] == 0.0


def test_timestamp_formats():
    assert ch.timestamp(0) == "0:00" and ch.timestamp(75) == "1:15" and ch.timestamp(3725) == "1:02:05"
    assert ch.timestamp(-3) == "0:00"


def test_keyword_title_picks_content_words():
    t = ch.keyword_title("Pricing is the first thing people ask about, pricing tiers and pricing pages.")
    assert t.startswith("Pricing") and len(t) <= ch.TITLE_MAX
    assert ch.keyword_title("") == "" and ch.keyword_title("the and of") == ""


def test_llm_titles_are_used_when_grounded():
    ask = lambda prompt: {"titles": ["Pricing tiers", "Hiring was hard", "Cutting churn 20 percent", "Roadmap with Maria", "Ship early"]}
    out = ch.chapters_for_reel(HIGHLIGHTS, SEGMENTS, ask=ask)
    assert [c["title"] for c in out] == ["Pricing tiers", "Hiring was hard", "Cutting churn 20 percent", "Roadmap with Maria", "Ship early"]
    assert out[0]["timestamp"] == "0:00" and out[1]["timestamp"] == "0:19"


def test_ungrounded_llm_title_falls_back_to_keywords():
    ask = lambda prompt: {"titles": ["Pricing tiers", "How Elon hired 500 people", "Churn", "Roadmap", "Ship early"]}
    out = ch.chapters_for_reel(HIGHLIGHTS, SEGMENTS, ask=ask)
    assert out[1]["title"].lower().startswith("hiring")          # keyword fallback, not the invented title
    assert "Elon" not in out[1]["title"]
    assert out[0]["title"] == "Pricing tiers"


def test_llm_wrong_count_or_failure_falls_back_to_keywords():
    for ask in (lambda p: {"titles": ["only one"]}, lambda p: None, lambda p: (_ for _ in ()).throw(RuntimeError("down"))):
        out = ch.chapters_for_reel(HIGHLIGHTS, SEGMENTS, ask=ask)
        assert len(out) == 5 and all(c["title"] for c in out)
        assert out[0]["title"].lower().startswith("pricing")


def test_titles_never_empty_even_without_speech():
    out = ch.chapters_for_reel(HIGHLIGHTS, [], ask=lambda p: None)
    assert [c["title"] for c in out][1:] == ["Part 2", "Part 3", "Part 4", "Part 5"]
    assert out[0]["title"] == "Part 1"


def test_title_cleaning_strips_timestamps_and_quotes():
    assert ch._clean_title('"0:45 - Big moment."') == "Big moment"
    assert len(ch._clean_title("word " * 40)) <= ch.TITLE_MAX


def test_format_chapters_is_youtube_ready():
    out = ch.chapters_for_reel(HIGHLIGHTS, SEGMENTS, ask=lambda p: None)
    lines = ch.format_chapters(out).splitlines()
    assert lines[0].startswith("0:00 ") and len(lines) == 5
    assert all(len(l.split(" ", 1)) == 2 for l in lines)


def test_make_reel_chapters_writes_file_and_survives_errors(tmp_path, monkeypatch):
    from engine.modes import clip_extract
    transcript = tmp_path / "t.json"
    transcript.write_text(json.dumps({"segments": SEGMENTS}), encoding="utf-8")
    import engine.chapters as chapters_mod
    monkeypatch.setattr(chapters_mod, "llm_titles", lambda texts, ask=None: None)
    out = clip_extract.make_reel_chapters(HIGHLIGHTS, str(transcript), None, str(tmp_path))
    assert len(out) == 5
    text = (tmp_path / "chapters.txt").read_text(encoding="utf-8")
    assert text.startswith("0:00 ") and len(text.strip().splitlines()) == 5
    # a reel too short for chapters: nothing is written
    other = tmp_path / "other"
    other.mkdir()
    assert clip_extract.make_reel_chapters(hl((0, 12)), str(transcript), None, str(other)) == []
    assert not os.path.exists(other / "chapters.txt")
    # a broken transcript path does not raise
    assert len(clip_extract.make_reel_chapters(HIGHLIGHTS, str(tmp_path / "missing.json"), None, str(other))) == 5


def test_keyword_title_skips_contractions_and_weak_words():
    t = ch.keyword_title("I'm back. You're here. That's excellent. Bone density loss happens because bones aren't loaded, "
                         "and exercise protects bone density and muscle.")
    assert "'" not in t and not any(w in t.lower() for w in ("back", "excellent", "here"))
    assert t.startswith("Bone")
