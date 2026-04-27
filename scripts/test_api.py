import os
import requests
from dotenv import load_dotenv

load_dotenv()

HF_API_KEY = os.getenv("HF_API_KEY")

def test_token():
    url = "https://huggingface.co/api/whoami-v2"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    r = requests.get(url, headers=headers)
    print(f"WhoAmI Status: {r.status_code}")
    print(f"WhoAmI Response: {r.text}")

def test_inference_api():
    # Try the old API just to see if it works at all
    url = "https://api-inference.huggingface.co/models/google/flan-t5-large"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    r = requests.post(url, headers=headers, json={"inputs": "Say hello"})
    print(f"Old Inference API Status: {r.status_code}")
    print(f"Old Inference API Response: {r.text}")

def test_router():
    # Try the new router with a very common model
    url = "https://router.huggingface.co/v1/chat/completions"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {
        "model": "meta-llama/Llama-3.2-3B-Instruct",
        "messages": [{"role": "user", "content": "Say hi"}]
    }
    r = requests.post(url, headers=headers, json=payload)
    print(f"Router API Status: {r.status_code}")
    print(f"Router API Response: {r.text}")

def test_standard_openai():
    # Many HF models now support /v1/chat/completions on the main inference domain
    url = "https://api-inference.huggingface.co/v1/chat/completions"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {
        "model": "meta-llama/Llama-3.2-3B-Instruct",
        "messages": [{"role": "user", "content": "Say hi"}]
    }
    r = requests.post(url, headers=headers, json=payload)
    print(f"Standard OpenAI API Status: {r.status_code}")
    print(f"Standard OpenAI API Response: {r.text}")

if __name__ == "__main__":
    test_token()
    test_inference_api()
    test_router()
    test_standard_openai()
