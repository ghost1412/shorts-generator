import requests
import os
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("HF_API_KEY")
url = "https://router.huggingface.co/v1/chat/completions"
headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

models = [
    "meta-llama/Llama-3.2-3B-Instruct",
    "meta-llama/Llama-3.1-8B-Instruct",
    "mistralai/Mistral-7B-Instruct-v0.3",
    "microsoft/Phi-3-mini-4k-instruct"
]

for model in models:
    payload = {"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 10}
    try:
        r = requests.post(url, headers=headers, json=payload)
        print(f"Model {model}: {r.status_code}")
        if r.status_code != 200:
            print(f"  Error: {r.text}")
    except Exception as e:
        print(f"Model {model} failed: {e}")
