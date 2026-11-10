import io

from engine import pipeline


class Tty(io.StringIO):
    def isatty(self):
        return True


def test_star_hint_only_in_a_terminal_and_can_be_switched_off(monkeypatch):
    monkeypatch.delenv("SHORTSFLOW_NO_STAR_HINT", raising=False)
    assert pipeline.star_hint(io.StringIO()) is False            # a pipe or a log: nothing printed
    out = Tty()
    assert pipeline.star_hint(out) is True
    assert "github.com/ghost1412/shorts-generator" in out.getvalue()
    monkeypatch.setenv("SHORTSFLOW_NO_STAR_HINT", "1")
    assert pipeline.star_hint(Tty()) is False


def test_description_footer_is_opt_in_and_in_the_scheduled_workflow():
    import os
    src = open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "engine", "modes", "generate.py"), encoding="utf-8").read()
    assert 'os.getenv("SHORTSFLOW_DESCRIPTION_FOOTER")' in src            # nothing is added unless the variable is set
    wf = open(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".github", "workflows", "daily_generate.yml"), encoding="utf-8").read()
    assert "SHORTSFLOW_DESCRIPTION_FOOTER" in wf
