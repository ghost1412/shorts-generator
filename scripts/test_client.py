from huggingface_hub import InferenceClient
import os
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("HF_API_KEY")

client = InferenceClient(token=key)

try:
    print("Testing with meta-llama/Llama-3.2-3B-Instruct...")
    response = client.chat_completion(
        messages=[{"role": "user", "content": "Tell me 3 facts about space as JSON [{\"fact\": \"...\", \"truth\": true}]"}],
        model="meta-llama/Llama-3.2-3B-Instruct",
        max_tokens=200
    )
    print("SUCCESS!")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"FAILED: {e}")
