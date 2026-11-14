"""A Gemini model that times out is skipped, not retried 4 times (a hung outline call held whole runs for many minutes)."""
import requests

from engine import script_gen


def test_gemini_timeout_moves_to_next_model_without_retrying(monkeypatch):
    calls = []

    def fake_post(url, **kw):
        calls.append((url, kw.get("timeout")))
        raise requests.exceptions.ReadTimeout("slow")

    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(script_gen, "GEMINI_API_KEY", "x", raising=False)
    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr("time.sleep", lambda s: None)
    for name in ("DEEPSEEK_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "HF_API_KEY", "HUGGINGFACE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.setattr(script_gen, name, None, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    try:
        script_gen.get_llm_response("p", timeout=5)
    except Exception:
        pass
    gemini = [c for c in calls if "generativelanguage" in c[0]]
    assert len(gemini) == 4            # one try per model, not 4 x 4
    assert all(t == 5 for _, t in gemini)
