import types

import pytest

from engine import groq_llm


class Resp:
    def __init__(self, status=200, body=None, text=""):
        self.status_code, self._body, self.text = status, body or {}, text

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            err = requests.HTTPError(f"{self.status_code} Client Error")
            err.response = self
            raise err


def answer(text):
    return Resp(200, {"choices": [{"message": {"content": text}}]})


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(groq_llm, "_working_model", None)
    monkeypatch.delenv("GROQ_MODEL", raising=False)


def test_skips_a_retired_model_and_remembers_the_working_one(monkeypatch):
    used = []

    def post(url, headers, json, timeout):
        used.append(json["model"])
        if json["model"] == "openai/gpt-oss-120b":
            return Resp(404, text='{"error":{"message":"The model `openai/gpt-oss-120b` does not exist"}}')
        return answer("hello")

    import requests
    monkeypatch.setattr(requests, "post", post)
    assert groq_llm.call_groq("k", "hi") == "hello"
    assert used == ["openai/gpt-oss-120b", "llama-3.3-70b-versatile"]
    used.clear()
    assert groq_llm.call_groq("k", "again") == "hello"
    assert used[0] == "llama-3.3-70b-versatile"          # remembered


def test_asks_groq_for_models_when_the_whole_preference_list_is_gone(monkeypatch):
    import requests
    gone = {m for m in groq_llm.MODEL_PREFERENCE}

    def post(url, headers, json, timeout):
        if json["model"] in gone:
            return Resp(404, text="model not found")
        return answer("from " + json["model"])

    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "get", lambda url, headers, timeout: Resp(200, {"data": [{"id": "whisper-large"}, {"id": "brand-new-70b"}]}))
    assert groq_llm.call_groq("k", "hi") == "from brand-new-70b"


def test_other_errors_are_raised_not_retried(monkeypatch):
    import requests
    calls = []
    monkeypatch.setattr(requests, "post", lambda url, headers, json, timeout: calls.append(1) or Resp(401, text="invalid api key"))
    with pytest.raises(requests.HTTPError):
        groq_llm.call_groq("bad", "hi")
    assert len(calls) == 1


def test_empty_answer_moves_on_to_the_next_model(monkeypatch):
    import requests
    seq = iter([answer(""), answer("ok")])
    monkeypatch.setattr(requests, "post", lambda url, headers, json, timeout: next(seq))
    assert groq_llm.call_groq("k", "hi") == "ok"


def test_a_per_minute_limit_waits_and_asks_again(monkeypatch):
    import requests
    waits, calls = [], []
    monkeypatch.setattr(groq_llm, "_sleep", lambda s: waits.append(s))

    def post(url, headers, json, timeout):
        calls.append(json["model"])
        if len(calls) < 3:
            r = Resp(429, text='{"error":{"message":"Rate limit reached ... on tokens per minute (TPM): Limit 8000, Used 7000, Requested 2000. Please try again in 5.2s."}}')
            r.headers = {"retry-after": "3"} if len(calls) == 1 else {}
            return r
        return answer("done")

    monkeypatch.setattr(requests, "post", post)
    assert groq_llm.call_groq("k", "hi") == "done"
    assert calls == ["openai/gpt-oss-120b"] * 3                 # the same model, asked again, not given up on
    assert waits == [4.0, 6.2]                                  # the header (3 s + 1), then "try again in 5.2s" (+ 1)


def test_rate_limit_retries_are_bounded_and_then_raised(monkeypatch):
    import requests
    monkeypatch.setattr(groq_llm, "_sleep", lambda s: None)
    calls = []
    monkeypatch.setattr(requests, "post", lambda url, headers, json, timeout: calls.append(1) or Resp(429, text="slow down"))
    with pytest.raises(requests.HTTPError):
        groq_llm.call_groq("k", "hi")
    assert len(calls) == groq_llm.RATE_RETRIES + 1


def test_a_request_above_the_models_limit_moves_to_the_next_model_without_waiting(monkeypatch):
    import requests
    slept, used = [], []
    monkeypatch.setattr(groq_llm, "_sleep", lambda s: slept.append(s))

    def post(url, headers, json, timeout):
        used.append(json["model"])
        if json["model"] == "openai/gpt-oss-120b":
            return Resp(413, text='{"error":{"message":"Request too large for model on tokens per minute (TPM): Limit 8000, Requested 12000"}}')
        return answer("ok")

    monkeypatch.setattr(requests, "post", post)
    assert groq_llm.call_groq("k", "hi") == "ok"
    assert used == ["openai/gpt-oss-120b", "llama-3.3-70b-versatile"] and slept == []


def test_wait_time_is_capped_and_has_a_default():
    class E(Exception):
        response = None
    assert groq_llm.wait_seconds(E(), 0) == 9.0 and groq_llm.wait_seconds(E(), 2) == 33.0
    e = E()
    e.response = Resp(429, text="try again in 4m10s")
    assert groq_llm.wait_seconds(e, 0) == groq_llm.MAX_WAIT
