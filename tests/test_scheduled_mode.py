import importlib.util
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("pick_scheduled_mode", ROOT / "scripts" / "pick_scheduled_mode.py")
psm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(psm)


def test_default_mix_uses_several_modes():
    rng = random.Random(1)
    seen = Counter(psm.pick("", rng) for _ in range(500))
    assert set(seen) == set(psm.DEFAULT_WEIGHTS)
    assert seen["FACTS"] < 250          # no longer every run


def test_single_mode_is_fixed():
    assert {psm.pick("wyr") for _ in range(20)} == {"WYR"}


def test_custom_weights_and_bad_input():
    rng = random.Random(2)
    assert {psm.pick("WYR:1,TRIVIA:1", rng) for _ in range(100)} == {"WYR", "TRIVIA"}
    assert psm.pick("a:b,c:-1", rng) in psm.DEFAULT_WEIGHTS


def test_default_modes_are_valid_cli_modes():
    import re
    main = (ROOT / "shortsflow" / "_main.py").read_text(encoding="utf-8")
    allowed = set(re.findall(r'"([A-Z0-9_]+)"', re.search(r'"--mode", choices=\[(.*?)\]', main).group(1)))
    assert set(psm.DEFAULT_WEIGHTS) <= allowed


def test_workflow_uses_picker():
    wf = (ROOT / ".github" / "workflows" / "daily_generate.yml").read_text(encoding="utf-8")
    assert "pick_scheduled_mode.py" in wf


def test_rotation_meets_the_weights_exactly_and_never_repeats_a_mode_in_a_row():
    picks = [psm.pick("", slot=n) for n in range(200)]
    counts = Counter(picks)
    assert set(counts) == set(psm.DEFAULT_WEIGHTS)
    total = sum(psm.DEFAULT_WEIGHTS.values())
    for mode, w in psm.DEFAULT_WEIGHTS.items():
        assert abs(counts[mode] - 200 * w / total) <= 1.01, (mode, counts[mode])      # as exact as whole picks allow
    assert all(a != b for a, b in zip(picks, picks[1:]))                               # no "spot the lie" three times in a row
    longest = max(len(list(g)) for k, g in __import__("itertools").groupby(picks))
    assert longest == 1


def test_rotation_is_deterministic_and_follows_custom_weights():
    assert [psm.pick("", slot=n) for n in range(30)] == [psm.pick("", slot=n) for n in range(30)]
    assert psm.pick("wyr", slot=5) == "WYR"                                            # a single fixed mode is untouched
    custom = Counter(psm.pick("WYR:3,TRIVIA:1", slot=n) for n in range(40))
    assert custom == {"WYR": 30, "TRIVIA": 10}
    assert psm.rotation_pick({"A": 1}, 7) == "A"


def test_slot_numbers_advance_every_four_hours():
    base = psm.SLOT_EPOCH + 10 * psm.SLOT_SECONDS
    assert psm.slot_number(base) == 10 and psm.slot_number(base + psm.SLOT_SECONDS - 1) == 10 and psm.slot_number(base + psm.SLOT_SECONDS) == 11
    assert psm.slot_number(0) == 0                                                     # never negative
    import subprocess, sys
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "pick_scheduled_mode.py"), ""], capture_output=True, text=True).stdout.strip()
    assert out in psm.DEFAULT_WEIGHTS
