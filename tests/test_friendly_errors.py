from engine.friendly_errors import explain_http_error, NO_LLM_HELP
from shortsflow.cli import clip_args


def test_known_failures_get_a_plain_fix():
    assert "no credits" in explain_http_error("402 Client Error: Payment Required for url", "Hugging Face")
    assert "GROQ_API_KEY" in explain_http_error("402 Payment Required")
    assert "rejected the API key" in explain_http_error("401 Unauthorized", "Groq")
    assert "rate limiting" in explain_http_error("429 Too Many Requests", "Gemini")
    assert "problems right now" in explain_http_error("503 Service Unavailable")
    assert "start Ollama" in explain_http_error("HTTPConnectionPool(host='localhost', port=11434): Max retries exceeded")


def test_unknown_errors_return_none_and_help_mentions_free_options():
    assert explain_http_error("something odd happened") is None
    assert "groq" in NO_LLM_HELP.lower() and "ollama" in NO_LLM_HELP.lower()


def test_clip_command_expands_to_pipeline_flags():
    flags = clip_args(["talk.mp4", "--count", "5", "--captions", "--clip_min", "20"])
    assert flags[:2] == ["--source_video", "talk.mp4"]
    assert ["--clip_count", "5"] == flags[flags.index("--clip_count"):flags.index("--clip_count") + 2]
    assert "--use_remotion" in flags and "--clip_min" in flags and "--skip-upload" in flags
    assert "--use_remotion" not in clip_args(["talk.mp4"])
