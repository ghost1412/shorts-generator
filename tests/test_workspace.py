import os

import pytest

from shortsflow import cli, workspace


@pytest.fixture
def fake_bundle(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    (bundle / "assets" / "avatars").mkdir(parents=True)
    (bundle / "assets" / "avatars" / "cat.png").write_bytes(b"png")
    (bundle / "remotion-video" / "src").mkdir(parents=True)
    (bundle / "remotion-video" / "src" / "Root.tsx").write_text("root")
    (bundle / "env.example").write_text("GEMINI_API_KEY=your_gemini_key_here\n")
    monkeypatch.setattr(workspace, "BUNDLE", str(bundle))
    monkeypatch.delenv("SHORTSFLOW_HOME", raising=False)
    return bundle


def test_bootstrap_copies_bundle_and_creates_env(fake_bundle, tmp_path, monkeypatch):
    home = tmp_path / "home"
    assert workspace.bootstrap(str(home)) == str(home)
    assert (home / "assets" / "avatars" / "cat.png").read_bytes() == b"png"
    assert (home / "remotion-video" / "src" / "Root.tsx").exists()
    assert "GEMINI_API_KEY" in (home / ".env").read_text()
    assert os.environ["SHORTSFLOW_HOME"] == str(home)
    monkeypatch.delenv("SHORTSFLOW_HOME")


def test_bootstrap_never_overwrites_user_files(fake_bundle, tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "assets" / "avatars").mkdir(parents=True)
    (home / "assets" / "avatars" / "cat.png").write_bytes(b"mine")
    (home / ".env").write_text("GEMINI_API_KEY=real\n")
    workspace.bootstrap(str(home))
    assert (home / "assets" / "avatars" / "cat.png").read_bytes() == b"mine"
    assert (home / ".env").read_text() == "GEMINI_API_KEY=real\n"
    monkeypatch.delenv("SHORTSFLOW_HOME")


def test_resolve_home(fake_bundle, tmp_path, monkeypatch):
    assert workspace.resolve_home().endswith("shortsflow")
    monkeypatch.setenv("SHORTSFLOW_HOME", str(tmp_path / "x"))
    assert workspace.resolve_home() == str(tmp_path / "x")


def test_checkout_is_its_own_workspace(monkeypatch):
    monkeypatch.setattr(workspace, "BUNDLE", "/nonexistent/bundle")
    monkeypatch.delenv("SHORTSFLOW_HOME", raising=False)
    assert workspace.is_checkout() and workspace.resolve_home() == workspace.REPO_ROOT


def test_doctor_ignores_placeholder_keys(tmp_path, monkeypatch):
    for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY", "HF_API_KEY", "PEXELS_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    (tmp_path / ".env").write_text("GEMINI_API_KEY=your_gemini_key_here\nPEXELS_API_KEY=abc123\n")
    result = {label: ok for label, ok, _ in workspace.doctor(str(tmp_path))}
    assert result["An LLM key (Gemini/Groq/OpenAI/HF) or local Ollama"] is False
    assert result["PEXELS_API_KEY (stock footage)"] is True


def test_cli_version_and_usage(capsys):
    cli.main(["--version"])
    assert capsys.readouterr().out.startswith("shortsflow ")
    cli.main([])
    assert "shortsflow init" in capsys.readouterr().out


def test_placeholder_keys_in_env_are_commented_out_but_real_ones_stay(tmp_path):
    env = tmp_path / ".env"
    env.write_text("GEMINI_API_KEY=your_gemini_api_key_here\nGROQ_API_KEY=gsk_real123\nPEXELS_API_KEY=your_pexels_api_key_here # free\n"
                   "LLM_PROVIDER=auto # 'auto'\nHF_API_KEY=\n", encoding="utf-8")
    assert workspace.comment_out_placeholders(str(env)) == 2
    text = env.read_text(encoding="utf-8")
    assert "# GEMINI_API_KEY=your_gemini_api_key_here" in text and "# PEXELS_API_KEY=your_pexels_api_key_here # free" in text
    assert "\nGROQ_API_KEY=gsk_real123\n" in text and "LLM_PROVIDER=auto" in text
    assert workspace.comment_out_placeholders(str(env)) == 0          # idempotent
    assert workspace.comment_out_placeholders(str(tmp_path / "missing.env")) == 0


def test_bootstrap_cleans_the_workspace_env(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "is_checkout", lambda: False)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "env.example").write_text("GEMINI_API_KEY=your_gemini_api_key_here\nPEXELS_API_KEY=real\n")
    monkeypatch.setattr(workspace, "BUNDLE", str(bundle))
    home = tmp_path / "home"
    workspace.bootstrap(str(home))
    text = (home / ".env").read_text()
    assert "# GEMINI_API_KEY=your_gemini_api_key_here" in text and "\nPEXELS_API_KEY=real" in text
