import random

from engine import puzzle_variety as pv


def test_fresh_avoids_recent_picks_and_remembers(tmp_path):
    path = str(tmp_path / "h.json")
    rng = random.Random(1)
    opts = ["a", "b", "c", "d", "e", "f"]
    picks = [pv.fresh(opts, "k", rng=rng, path=path) for _ in range(3)]
    assert len(set(picks)) == 3                      # the last half of the list is skipped, so no repeat within 3 picks
    assert pv.fresh(opts, "other", rng=rng, path=path) in opts


def test_fresh_works_with_one_option_and_a_broken_history_file(tmp_path):
    path = tmp_path / "h.json"
    path.write_text("not json")
    assert pv.fresh(["only"], "k", path=str(path)) == "only"
    assert pv.fresh(["only"], "k", path=str(path)) == "only"
