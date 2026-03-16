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
    "HuggingFaceH4/zephyr-7b-beta"
]

with open("router_results.txt", "w") as f:
    for model in models:
        payload = {"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 10}
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=10)
            f.write(f"{model}: {r.status_code}\n")
            if r.status_code != 200:
                f.write(f"  Error: {r.text}\n")
            else:
                f.write(f"  Success: {r.json()['choices'][0]['message']['content']}\n")
        except Exception as e:
            f.write(f"{model} failed: {e}\n")
