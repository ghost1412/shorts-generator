"""Groq chat completions that survive Groq retiring a model.

Groq removes models from time to time (llama-3.3-70b-versatile was removed in 2026 and the daily channel failed on its 404 for
days), so this tries a preference list and, when every entry is gone, whichever chat model the key can see. The model that
worked is remembered for the rest of the run. Only needs `requests`.
"""
import os

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS_URL = "https://api.groq.com/openai/v1/models"
MODEL_PREFERENCE = ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "openai/gpt-oss-20b", "qwen/qwen3.8-27b", "llama-3.1-8b-instant"]
_NOT_CHAT = ("whisper", "guard", "tts", "orpheus")
_working_model = None


def missing_model(exc):
    resp = getattr(exc, "response", None)
    return resp is not None and resp.status_code in (400, 404) and "model" in (resp.text or "").lower()


def list_chat_models(api_key):
    import requests
    r = requests.get(MODELS_URL, headers={"Authorization": f"Bearer {api_key}"}, timeout=20)
    r.raise_for_status()
    return [m["id"] for m in r.json().get("data", []) if not any(x in m["id"] for x in _NOT_CHAT)]


def _chat(api_key, model, prompt, system_prompt, max_tokens, temperature, timeout):
    import requests
    messages = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + [{"role": "user", "content": prompt}]
    payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    if "gpt-oss" in model:
        payload["reasoning_effort"] = "low"     # these are reasoning models; keep the token budget for the answer
    r = requests.post(GROQ_URL, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                      json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()["choices"][0]["message"].get("content") or ""


def call_groq(api_key, prompt, system_prompt=None, preferred=None, max_tokens=4096, temperature=0.3, timeout=120):
    """Answer text from Groq. Raises the last error when no model works."""
    global _working_model
    queue = list(dict.fromkeys(m for m in (preferred, os.getenv("GROQ_MODEL"), _working_model, *MODEL_PREFERENCE) if m))
    tried, last, listed = [], None, False
    while queue:
        model = queue.pop(0)
        tried.append(model)
        try:
            text = _chat(api_key, model, prompt, system_prompt, max_tokens, temperature, timeout)
            if not text.strip():
                raise RuntimeError(f"Groq model {model} returned an empty answer")
            _working_model = model
            return text
        except Exception as e:
            last = e
            if not (missing_model(e) or isinstance(e, RuntimeError)):
                raise
            if not queue and not listed:   # preference list used up: ask Groq what this key can use
                listed = True
                try:
                    queue = [m for m in list_chat_models(api_key) if m not in tried]
                except Exception:
                    pass
    raise last if last else RuntimeError("No Groq model available")
