from engine import speech_model as sm


def test_cpu_gets_the_small_model_and_gpu_the_medium_one(monkeypatch):
    monkeypatch.delenv("SHORTSFLOW_WHISPER_MODEL", raising=False)
    assert sm.pick_model("cpu") == "small"
    assert sm.pick_model("cuda") == "medium"


def test_env_override_wins(monkeypatch):
    monkeypatch.setenv("SHORTSFLOW_WHISPER_MODEL", "base")
    assert sm.pick_model("cuda") == "base" and sm.pick_model("cpu") == "base"


def test_download_notice_only_when_the_model_is_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    msg = sm.download_notice("medium")
    assert "Downloading the speech model 'medium'" in msg and "1.5 GB" in msg
    assert "465 MB" in sm.download_notice("small")
    (tmp_path / "whisper").mkdir()
    (tmp_path / "whisper" / "small.pt").write_bytes(b"x")
    assert sm.download_notice("small") is None
