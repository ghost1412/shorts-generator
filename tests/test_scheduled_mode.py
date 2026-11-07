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
