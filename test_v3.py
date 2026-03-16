import os, requests
from dotenv import load_dotenv
load_dotenv()
key = os.getenv("HF_API_KEY")

models = [
    "mistralai/Mistral-7B-Instruct-v0.3",
    "google/gemma-2-2b-it",
    "meta-llama/Llama-3.2-3B-Instruct"
]

for model in models:
    for base_url in [
        "https://api-inference.huggingface.co/models/",
        "https://router.huggingface.co/v1/chat/completions",
    ]:
        headers = {"Authorization": f"Bearer {key}"}
        if "chat/completions" in base_url:
            payload = {"model": model, "messages": [{"role": "user", "content": "hi"}]}
            url = base_url
        else:
            payload = {"inputs": "hi"}
            url = base_url + model
            
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=10)
            print(f"{model} | {url.split('/')[-1]}: {r.status_code}")
            if r.status_code == 200:
                print(f"  SUCCESS on {url}")
        except:
            print(f"{model} | {url.split('/')[-1]}: ERROR")
