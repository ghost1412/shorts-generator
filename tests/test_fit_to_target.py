from engine.analysis import fit_to_target


def h(start, dur, score):
    return {"start": float(start), "end": float(start + dur), "final_score": score}


def total(items):
    return sum(i["end"] - i["start"] for i in items)


def test_total_lands_within_tolerance_instead_of_overshooting_by_30_percent():
    cands = [h(0, 50, 9), h(100, 50, 8), h(200, 50, 7), h(300, 50, 6), h(400, 50, 5), h(500, 50, 4)]
    out = fit_to_target(cands, 240)
    assert total(out) <= 240 * 1.08 + 1e-6 and total(out) >= 240 * 0.92


def test_best_scores_are_preferred_and_last_one_is_trimmed_to_fit():
    out = fit_to_target([h(0, 100, 9), h(200, 100, 8), h(400, 100, 7)], 240)
    assert [o["start"] for o in out] == [0.0, 200.0, 400.0][:len(out)]
    assert abs(total(out) - 240 * 1.08) < 1e-6
    assert out[-1].get("trimmed") is True and out[-1]["end"] - out[-1]["start"] >= 15


def test_skips_a_segment_when_too_little_room_is_left_to_trim():
    out = fit_to_target([h(0, 250, 9), h(300, 100, 8)], 240)   # 259.2 ceiling: 250 fits, nothing else is needed
    assert [o["start"] for o in out] == [0.0]


def test_counts_what_was_already_chosen_and_does_not_mutate_input():
    src = [h(0, 60, 5)]
    out = fit_to_target(src, 240, already=230)
    assert out == [] or total(out) <= 240 * 1.08 - 230 + 1e-6
    assert src == [h(0, 60, 5)]


def test_empty_input():
    assert fit_to_target([], 240) == []


def test_order_for_mode_keeps_shorts_best_first_and_puts_long_form_in_story_order():
    from engine.analysis import order_for_mode
    items = [h(928, 45, 9), h(168, 22, 8), h(448, 105, 7)]
    assert [x["start"] for x in order_for_mode(items, "shorts")] == [928.0, 168.0, 448.0]
    assert [x["start"] for x in order_for_mode(items, "long")] == [168.0, 448.0, 928.0]
    assert order_for_mode([], "long") == []
