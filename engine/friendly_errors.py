"""Plain-language explanations for the errors a first-time user actually hits (bad key, no credits, rate limit, offline)."""
import re


def explain_http_error(error, provider="the AI service"):
    """One-line fix for an LLM/API failure, or None when nothing useful can be said. `error` is an exception or text."""
    text = str(error)
    code = None
    m = re.search(r"\b(40[0-9]|42[0-9]|50[0-9])\b", text)
    if m:
        code = int(m.group(1))
    low = text.lower()
    if code == 402 or "payment required" in low or "insufficient" in low and "credit" in low:
        return (f"{provider} says this account has no credits left. Add credits there, or use a free option instead: "
                "put a free GROQ_API_KEY (console.groq.com) in your .env, or install Ollama (ollama.com) to run it on your PC.")
    if code in (401, 403) or "invalid api key" in low or "unauthorized" in low:
        return (f"{provider} rejected the API key. Copy the key again with no spaces or quotes into your .env file "
                "(and check it has not expired).")
    if code == 429 or "rate limit" in low or "quota" in low:
        return (f"{provider} is rate limiting you (free-tier limit reached). Wait a minute and retry, or add a second key "
                "such as GROQ_API_KEY as a fallback.")
    if code and code >= 500:
        return f"{provider} is having problems right now (error {code}). Retry in a few minutes."
    if any(w in low for w in ("connection refused", "connection error", "max retries", "timed out", "timeout", "name resolution",
                              "getaddrinfo")):
        return (f"Could not reach {provider}. Check your internet connection"
                + (" - or start Ollama if you meant to use it locally." if "11434" in text or "ollama" in low else "."))
    return None


NO_LLM_HELP = (
    "No AI text provider answered. Clipping long videos into shorts works without one, but titles, descriptions and idea-to-video "
    "modes need one. Easiest free fixes: (1) get a free key at console.groq.com and add GROQ_API_KEY=... to your .env, "
    "or (2) install Ollama from ollama.com and run `ollama pull qwen2.5:7b`. Run `shortsflow doctor` to check your setup."
)
