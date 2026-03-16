import os, requests
from dotenv import load_dotenv
load_dotenv()
key = os.getenv("HF_API_KEY")

for url in [
    "https://api-inference.huggingface.co/models/google/flan-t5-large",
    "https://router.huggingface.co/v1/chat/completions",
    "https://api-inference.huggingface.co/v1/chat/completions"
]:
    headers = {"Authorization": f"Bearer {key}"}
    if "chat/completions" in url:
        r = requests.post(url, headers=headers, json={"model": "meta-llama/Llama-3.2-3B-Instruct", "messages": [{"role": "user", "content": "hi"}]})
    else:
        r = requests.post(url, headers=headers, json={"inputs": "hi"})
    print(f"{url.split('/')[-1]}: {r.status_code}")
