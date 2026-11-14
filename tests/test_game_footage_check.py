"""Moments that look like real filmed footage are flagged in game mode (never removed), and the flag reaches the plan."""
from engine import plan, visual_context as vc


def _ask(answers):
    seen = iter(answers)

    def ask(frames, model, about, prompt=None):
        assert prompt == vc.GAME_PROMPT
        return next(seen)
    return ask


def test_real_footage_is_flagged_and_nothing_is_removed():
    hl = [{"start": 1, "end": 20}, {"start": 30, "end": 50}, {"start": 60, "end": 80}]
    out = vc.flag_non_game("v.mp4", hl, ask=_ask(["GAME", "REAL.", "unsure"]), model="m", grab=lambda *a: [b"x"])
    assert len(out) == 3
    assert [bool(h.get("warning")) for h in out] == [False, True, False]
    assert "warning" not in hl[1]                   # the input is not modified


def test_no_backend_or_no_answer_leaves_highlights_unchanged(monkeypatch):
    monkeypatch.setattr(vc, "choose_backend", lambda: (None, None, "none"))
    hl = [{"start": 1, "end": 20}]
    assert vc.flag_non_game("v.mp4", hl) == hl
    out = vc.flag_non_game("v.mp4", hl, ask=_ask([""]), model="m", grab=lambda *a: [])
    assert "warning" not in out[0]


def test_warning_is_shown_in_the_plan(tmp_path):
    hl = [{"start": 1, "end": 20, "warning": vc.WARN_REAL, "reason": "steady speech"}, {"start": 30, "end": 50}]
    plan.write_plan(str(tmp_path), hl, "v.mp4")
    moments = plan.read_plan(str(tmp_path))["moments"]
    assert moments[0]["reason"].startswith("this moment looks like real filmed footage")
    assert "steady speech" in moments[0]["reason"] and moments[1]["reason"] == ""
