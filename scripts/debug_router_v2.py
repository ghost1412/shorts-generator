import requests
import os
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("HF_API_KEY")
url = "https://router.huggingface.co/v1/chat/completions"
headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

models = [
    "meta-llama/Llama-3.2-3B-Instruct",
    "meta-llama/Llama-3.2-1B-Instruct",
    "google/gemma-2-2b-it",
    "mistralai/Mistral-7B-Instruct-v0.2"
]

results = []
for model in models:
    payload = {"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 10}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        results.append(f"{model}: {r.status_code}")
        if r.status_code != 200:
            results.append(f"  Error: {r.text[:100]}")
    except Exception as e:
        results.append(f"{model} failed: {e}")

print("\n".join(results))
