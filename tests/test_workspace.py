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
