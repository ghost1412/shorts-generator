from engine.analysis import pick_backfill


def seg(start, end, score=0.5):
    return {"start": start, "end": end, "norm_score": score, "norm_audio": 0.0}


def test_prefers_a_clip_away_from_the_one_already_chosen():
    chosen = [{"start": 150.0, "end": 193.0}]
    cands = [seg(194.0, 237.0, 0.9), seg(600.0, 640.0, 0.5)]  # best-scoring candidate is the adjacent window
    out = pick_backfill(cands, chosen, 1)
    assert [(o["start"], o["end"]) for o in out] == [(600.0, 640.0)]


def test_falls_back_to_a_neighbour_when_nothing_else_exists():
    out = pick_backfill([seg(194.0, 237.0)], [{"start": 150.0, "end": 193.0}], 1)
    assert [(o["start"], o["end"]) for o in out] == [(194.0, 237.0)]


def test_never_overlaps_and_skips_tiny_segments():
    chosen = [{"start": 100.0, "end": 140.0}]
    out = pick_backfill([seg(120.0, 160.0), seg(300.0, 305.0)], chosen, 2)
    assert out == []


def test_fills_only_what_is_needed_and_picks_distinct_clips():
    cands = [seg(10, 50, 0.9), seg(55, 95, 0.8), seg(300, 340, 0.7), seg(700, 740, 0.6)]
    out = pick_backfill(cands, [], 2)
    assert [(o["start"], o["end"]) for o in out] == [(10, 50), (300, 340)]  # 55-95 is within 30 s of 10-50
    assert all(o["reason"] == "Energy Peak (Backfill)" for o in out)
