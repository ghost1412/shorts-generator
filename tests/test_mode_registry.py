"""Every mode the CLI accepts must either be handled somewhere in engine/ or be explicitly marked as not implemented."""
import glob
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "shortsflow" / "_main.py").read_text(encoding="utf-8")


def cli_modes():
    block = re.search(r'"--mode".*?choices=\[(.*?)\]', MAIN, re.S).group(1)
    return re.findall(r'"([A-Z_0-9]+)"', block)


def not_implemented():
    m = re.search(r"NOT_IMPLEMENTED_MODES = \((.*?)\)", MAIN, re.S)
    return set(re.findall(r'"([A-Z_0-9]+)"', m.group(1))) if m else set()


def engine_sources():
    files = glob.glob(str(ROOT / "engine" / "**" / "*.py"), recursive=True)
    return "\n".join(Path(p).read_text(encoding="utf-8", errors="ignore") for p in files)


def test_every_cli_mode_has_a_handler_or_is_marked_not_implemented():
    src = engine_sources()
    missing = [m for m in cli_modes() if m not in not_implemented() and not re.search(r'["\']%s["\']' % m, src)]
    assert not missing, f"modes accepted by --mode but handled nowhere in engine/: {missing}"


def test_not_implemented_modes_are_still_listed_so_users_get_the_clear_error():
    assert not_implemented() <= set(cli_modes())
    assert {"PODCAST", "SPLIT_SCREEN"} <= not_implemented()
    assert "DUB" not in not_implemented()


def test_docs_do_not_advertise_not_implemented_modes_as_working():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for mode in not_implemented():
        pattern = r"^\s*(py|python3?) main\.py[^\n]*--mode " + mode + r"\b"
        assert not re.search(pattern, readme, re.M), f"README still shows a runnable --mode {mode} example"
