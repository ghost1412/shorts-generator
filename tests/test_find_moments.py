from engine.find_moments import build_windows, find_moments, keyword_matches

SEGMENTS = [
    {"start": 0, "end": 10, "text": "Welcome to the show everybody."},
    {"start": 10, "end": 20, "text": "Today we cover the pricing of our product."},
    {"start": 20, "end": 30, "text": "Pricing tiers start at ten dollars."},
    {"start": 30, "end": 60, "text": "Totally different topic about gardening and tomatoes."},
    {"start": 60, "end": 75, "text": "Another word on pricing and discounts for teams."},
    {"start": 75, "end": 90, "text": "Thanks for watching, bye."},
]


def test_build_windows_merges_short_segments():
    w = build_windows(SEGMENTS, window=15)
    assert w[0]["start"] == 0 and w[0]["end"] == 10  # 0-10 then adding 10-20 would exceed 15s
    assert all(x["end"] > x["start"] for x in w)


def test_keyword_fallback_finds_pricing_not_gardening():
    clips = find_moments(SEGMENTS, "where they discuss pricing", clip_count=5, target_duration=40, min_duration=10)
    assert clips and all("garden" not in str(c) for c in clips)
    assert any(c["start"] <= 20 <= c["end"] for c in clips)
    assert all(c["end"] - c["start"] <= 40 for c in clips)
    assert "pricing" in clips[0]["reason"]


def test_llm_results_are_used_and_filtered():
    windows = build_windows(SEGMENTS)
    pricing = next(i for i, w in enumerate(windows) if "tiers" in w["text"] or "Pricing" in w["text"])

    def ask(prompt):
        return [{"index": pricing, "score": 9, "reason": "states the price"},
                {"index": 0, "score": 2, "reason": "weak"},      # below threshold, dropped
                {"index": 999, "score": 9, "reason": "bogus"}]   # out of range, dropped

    clips = find_moments(SEGMENTS, "price", ask=ask, min_duration=5)
    assert len(clips) == 1 and clips[0]["viral_score"] == 90
    assert clips[0]["hook_text"] == "states the price"


def test_llm_failure_falls_back_to_keywords():
    def ask(prompt):
        raise RuntimeError("no providers")

    assert find_moments(SEGMENTS, "gardening tomatoes", ask=ask, min_duration=5)


def test_empty_query_or_transcript():
    assert find_moments(SEGMENTS, "  ") == []
    assert find_moments([], "pricing") == []
    assert keyword_matches(build_windows(SEGMENTS), "the a of") == []
