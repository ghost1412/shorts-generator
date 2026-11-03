"""Check which LLM providers answer with the keys in the environment (used by the manual "LLM check" workflow).

Never prints a key. For Groq it also lists the chat models the key can use, so a retired default model is easy to spot.

    python scripts/llm_check.py
"""
import json
import os
import sys

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.friendly_errors import explain_http_error  # noqa: E402


def ask(name, url, key, model):
    if not key:
        print(f"{name:12} no key set")
        return
    try:
        r = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                          json={"model": model, "messages": [{"role": "user", "content": "Reply with the word OK."}], "max_tokens": 5},
                          timeout=30)
        r.raise_for_status()
        print(f"{name:12} OK  ({model})")
    except Exception as e:
        print(f"{name:12} FAILED ({model}): {e}")
        hint = explain_http_error(e, name)
        if hint:
            print(f"{'':12} -> {hint}")


def groq_models(key):
    r = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {key}"}, timeout=30)
    r.raise_for_status()
    return sorted(m["id"] for m in r.json().get("data", []))


def main():
    groq = os.getenv("GROQ_API_KEY", "")
    if groq:
        # the same code path the pipeline uses (picks a working model by itself)
        from engine import groq_llm
        try:
            text = groq_llm.call_groq(groq, 'Return only this JSON: {"ok": true, "n": 3}', max_tokens=300)
            print(f"{'Groq':12} OK  (model used: {groq_llm._working_model}) answer: {text.strip()[:80]!r}")
        except Exception as e:
            print(f"{'Groq':12} FAILED: {e}")
            hint = explain_http_error(e, "Groq")
            if hint:
                print(f"{'':12} -> {hint}")
    else:
        print(f"{'Groq':12} no key set")
    if groq:
        try:
            ids = [m for m in groq_models(groq) if not any(x in m for x in ("whisper", "guard", "tts", "orpheus"))]
            print("Groq chat models for this key:", json.dumps(ids))
        except Exception as e:
            print("Groq model list failed:", e)
    ask("HuggingFace", "https://router.huggingface.co/v1/chat/completions", os.getenv("HF_API_KEY", ""), "meta-llama/Llama-3.1-8B-Instruct")
    gem = os.getenv("GEMINI_API_KEY", "")
    print(f"{'Gemini':12} {'key set (not tested here)' if gem else 'no key set'}")


if __name__ == "__main__":
    main()
