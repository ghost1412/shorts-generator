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
