import types

import pytest

from engine import steps_recap as sr
from engine import trip_recap as tr

SAMPLE = """\
# a note that is ignored
Title: Build a bird house
Hook: Done in one afternoon
Needs: 4 pine boards | 30 screws
- wood glue
- a drill
End: Ready to hang!

1. Cut the boards | Cut four 20 cm sides and two 15 cm roof pieces
2) Drill the hole | 3 cm hole, 12 cm above the floor
Step 3: Assemble | Glue, then 6 screws per side
4. Hang it up
"""


def test_a_steps_file_is_read_into_a_plan():
    p = sr.parse_steps(SAMPLE)
    assert p["title"] == "Build a bird house" and p["hook"] == "Done in one afternoon" and p["end"] == "Ready to hang!"
    assert p["needs"] == ["4 pine boards", "30 screws", "wood glue", "a drill"] and p["needs_title"] == "What you need"
    assert p["steps"] == [("Cut the boards", "Cut four 20 cm sides and two 15 cm roof pieces"), ("Drill the hole", "3 cm hole, 12 cm above the floor"),
                          ("Assemble", "Glue, then 6 screws per side"), ("Step 4", "Hang it up")]        # no "|": the text is the caption


def test_the_needs_card_takes_its_heading_from_the_key():
    assert sr.parse_steps("Ingredients: 2 eggs | 1 cup flour\n1. Mix | Mix well")["needs_title"] == "Ingredients"
    assert sr.parse_steps("Tools: drill\n1. a | b")["needs_title"] == "Tools"
    assert sr.parse_steps("")["steps"] == [] and sr.parse_steps(None)["steps"] == []


def _args(tmp_path, text=SAMPLE, **kw):
    f = tmp_path / "steps.txt"
    f.write_text(text, encoding="utf-8")
    base = dict(steps_file=str(f), trip_name="", trip_stops=None, recap_lines="", recap_hook="", recap_ingredients="", recap_ingredients_title="",
                recap_end_text="", recap_pace=None, recap_opening=None, recap_end=None, recap_style="auto", recap_aspect=None, recap_length=60,
                trip_videos=[], recap_kind="trip")
    base.update(kw)
    return types.SimpleNamespace(**base)


def test_the_steps_file_fills_the_options_and_the_step_by_step_defaults(tmp_path):
    a = _args(tmp_path)
    plan = sr.apply_steps(a)
    assert len(plan["steps"]) == 4
    assert a.recap_kind == "steps" and a.trip_name == "Build a bird house" and a.recap_hook == "Done in one afternoon"
    assert a.trip_stops == "Cut the boards|Drill the hole|Assemble|Step 4"
    assert a.recap_lines.split("|")[0].startswith("Cut four 20 cm") and len(a.recap_lines.split("|")) == 4          # one caption per step: the order holds
    assert a.recap_ingredients == "4 pine boards|30 screws|wood glue|a drill" and a.recap_ingredients_title == "What you need"
    assert (a.recap_pace, a.recap_opening, a.recap_end, a.recap_style, a.recap_aspect, a.recap_safe_text) == ("fast", "result", "result", "cinematic", "9:16", True)
    assert a.recap_end_text == "Ready to hang!" and a.recap_length == 40                                              # 4 steps: the minimum length


def test_options_given_on_the_command_line_win_over_the_file(tmp_path):
    a = _args(tmp_path, trip_name="My title", recap_pace="normal", recap_style="hype", recap_aspect="16:9", recap_length=90, recap_hook="Mine",
              recap_end="none", recap_ingredients="1 thing")
    sr.apply_steps(a)
    assert a.trip_name == "My title" and a.recap_pace == "normal" and a.recap_style == "hype" and a.recap_aspect == "16:9"
    assert a.recap_length == 90 and a.recap_hook == "Mine" and a.recap_end == "none" and a.recap_ingredients == "1 thing"


def test_no_steps_file_changes_nothing_and_a_bad_file_says_why(tmp_path):
    a = _args(tmp_path, steps_file=None)
    assert sr.apply_steps(a) is None and a.recap_kind == "trip" and a.recap_pace is None
    with pytest.raises(ValueError, match="No steps found"):
        sr.apply_steps(_args(tmp_path, text="Title: only a title\nNeeds: nothing"))
    with pytest.raises(ValueError, match="Cannot read"):
        sr.apply_steps(types.SimpleNamespace(steps_file=str(tmp_path / "missing.txt")))


def test_a_mismatch_between_steps_and_folders_is_warned_about(tmp_path, capsys):
    folders = []
    for i in range(3):
        d = tmp_path / f"f{i}"
        d.mkdir()
        folders.append(str(d))
    sr.apply_steps(_args(tmp_path, trip_videos=folders))
    assert "4 steps in the steps file but 3 folders" in capsys.readouterr().out
    sr.apply_steps(_args(tmp_path, trip_videos=folders[:1]))                       # one folder of clips in filming order: no warning
    assert "folders of clips" not in capsys.readouterr().out


def test_the_recap_engine_receives_the_step_by_step_settings(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(tr, "make_recap", lambda paths, session_dir, **kw: seen.update(kw) or {"video": "x.mp4", "itinerary_md": None})
    monkeypatch.setattr(tr, "make_recap_versions", lambda *a, **k: seen.update(k) or [])
    a = _args(tmp_path, trip_videos=[str(tmp_path)], session_dir=str(tmp_path / "s"), recap_versions="one", recap_no_geocode=False, layout="auto")
    try:
        tr.run(a)
    except SystemExit:
        pass
    extras = seen.get("extras") or {}
    assert seen.get("kind") == "steps" and seen.get("trip_name") == "Build a bird house"
    assert extras.get("pace") == "fast" and extras.get("opening") == "result" and extras.get("end") == "result" and extras.get("safe") is True
    assert extras.get("ingredients") == "4 pine boards|30 screws|wood glue|a drill" and extras.get("ingredients_title") == "What you need"
    assert tr.get_kind("steps")["unit"] == "Step"


def test_the_command_line_has_the_steps_options():
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = open(os.path.join(root, "shortsflow", "_main.py"), encoding="utf-8").read()
    assert '"--steps_file"' in src and '"--recap_ingredients_title"' in src and '"steps"]' in src
