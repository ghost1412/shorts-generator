"""Groq chat completions that survive Groq retiring a model.

Groq removes models from time to time (llama-3.3-70b-versatile was removed in 2026 and the daily channel failed on its 404 for
days), so this tries a preference list and, when every entry is gone, whichever chat model the key can see. The model that
worked is remembered for the rest of the run. Only needs `requests`.
"""
import os
import re
import time

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS_URL = "https://api.groq.com/openai/v1/models"
MODEL_PREFERENCE = ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "openai/gpt-oss-20b", "qwen/qwen3.8-27b", "llama-3.1-8b-instant"]
_NOT_CHAT = ("whisper", "guard", "tts", "orpheus")
_working_model = None
RATE_RETRIES = 4          # how many times one model is tried again after "429 Too Many Requests"
MAX_WAIT = 65.0           # seconds: never wait longer than this for one retry (a minute's token allowance refills in a minute)
_sleep = time.sleep       # replaced in the tests


def missing_model(exc):
    resp = getattr(exc, "response", None)
    return resp is not None and resp.status_code in (400, 404) and "model" in (resp.text or "").lower()


def too_large(exc):
    """True when the request itself is above the model's limit (a bigger allowance is needed, waiting does not help)."""
    resp = getattr(exc, "response", None)
    text = (getattr(resp, "text", "") or "").lower()
    if resp is None:
        return False
    if resp.status_code == 413 or "request too large" in text:
        return True
    m = re.search(r"limit (\d+), (?:used \d+, )?requested (\d+)", text)
    return bool(m and int(m.group(2)) > int(m.group(1)))


def rate_limited(exc):
    resp = getattr(exc, "response", None)
    return resp is not None and resp.status_code == 429 and not too_large(exc)


def wait_seconds(exc, attempt):
    """How long to wait before trying again: Groq's Retry-After header, else the "try again in 5.2s" in its message, else a growing pause."""
    resp = getattr(exc, "response", None)
    headers = getattr(resp, "headers", None) or {}
    try:
        value = float(headers.get("retry-after") or headers.get("Retry-After"))
    except (TypeError, ValueError):
        value = None
    if value is None:
        m = re.search(r"try again in (?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?", (getattr(resp, "text", "") or "").lower())
        if m and (m.group(1) or m.group(2)):
            value = int(m.group(1) or 0) * 60 + float(m.group(2) or 0)
    if value is None:
        value = 8.0 * (2 ** attempt)
    return min(MAX_WAIT, max(1.0, value + 1.0))


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
    waits = 0
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
            if rate_limited(e) and waits < RATE_RETRIES:        # a per-minute allowance: wait for it to refill, then ask again
                pause = wait_seconds(e, waits)
                waits += 1
                print(f"[Log] Groq says slow down (429); waiting {pause:.0f}s, then trying {model} again ({waits}/{RATE_RETRIES}).")
                _sleep(pause)
                queue.insert(0, model)
                continue
            if too_large(e) and queue:                          # this model's allowance is below the request: another model may have more
                print(f"[Log] The request is above {model}'s token limit; trying the next model.")
                continue
            if not (missing_model(e) or isinstance(e, RuntimeError)):
                raise
            if not queue and not listed:   # preference list used up: ask Groq what this key can use
                listed = True
                try:
                    queue = [m for m in list_chat_models(api_key) if m not in tried]
                except Exception:
                    pass
    raise last if last else RuntimeError("No Groq model available")
