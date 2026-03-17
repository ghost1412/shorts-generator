import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

HF_API_KEY = os.getenv("HF_API_KEY")

def generate_mixed_facts(category="science"):
    """
    Generates 2 True facts and 1 False fact using LLM with robust fallbacks.
    Returns a list of dicts: {"fact": str, "truth": bool}
    """
    url = "https://router.huggingface.co/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }

    if not HF_API_KEY:
        print("DEBUG: HF_API_KEY is missing!")
        raise RuntimeError("HF_API_KEY is missing. Cannot generate facts.")

    model = "meta-llama/Llama-3.2-1B-Instruct" 
    
    prompt = f"""SPOT THE LIE! 🔍 One of these facts is a fake. Can you find it?
Generate three short, shocking facts about {category}. Exactly two must be true and one must be a believable lie.
If the category is '{category}' and it relates to anime/media, focus on specific plot points or "lore" (e.g., character actions or twists).
If the category relates to health or biology, focus on surprising scientific facts.
If the category relates to cooking, focus on kitchen secrets or food science.
Format as JSON ONLY. No other text. 
Example format:
[
  {{"fact": "...", "truth": true}},
  {{"fact": "...", "truth": true}},
  {{"fact": "...", "truth": false}}
]
"""
    
    max_retries = 2
    for attempt in range(max_retries + 1):
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500,
            "temperature": 0.7 + (attempt * 0.1)
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            if response.status_code != 200:
                print(f"DEBUG: API Error {response.status_code} - {response.text}")
            
            response.raise_for_status()
            
            try:
                response_json = response.json()
            except Exception as json_err:
                print(f"DEBUG: Attempt {attempt+1} - Failed to parse JSON. Response text: '{response.text}'")
                continue

            output = response_json["choices"][0]["message"]["content"]
            
            start = output.find("[")
            end = output.rfind("]") + 1
            if start == -1 or end <= 0:
                print(f"DEBUG: Attempt {attempt+1} - No JSON array found in output.")
                continue

            facts = json.loads(output[start:end])
            
            # VALIDATION: Ensure exactly 2 True and 1 False
            trues = [f for f in facts if f.get("truth") is True]
            falses = [f for f in facts if f.get("truth") is False]
            
            if len(trues) == 2 and len(falses) == 1:
                for f in facts:
                    f["fact"] = f["fact"].split(": ", 1)[-1] if ": " in f["fact"] else f["fact"]
                    if f["fact"].startswith(("1. ", "2. ", "3. ")):
                        f["fact"] = f["fact"][3:]
                return facts[:3]
            else:
                print(f"⚠️ Attempt {attempt+1}: LLM generated wrong counts ({len(trues)}T, {len(falses)}F). Retrying...")
                
        except Exception as e:
            print(f"💡 Attempt {attempt+1} failed ({type(e).__name__}: {e})")
            if attempt == max_retries:
                break

    print("❌ All API attempts failed or gave wrong counts. Failing to avoid low-quality upload.")
    raise RuntimeError("LLM Fact Generation failed to produce valid 2T/1F ratio after retries.")

def generate_fallback_facts(category): # [DELETE] Removing fallback function entirely
    pass

def generate_story(category="history"):
    """
    Generates a single, shocking true story about the category.
    Returns: {"story": str, "title": str}
    """
    url = "https://router.huggingface.co/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }

    if not HF_API_KEY:
        print("DEBUG: HF_API_KEY is missing for story!")
        raise RuntimeError("HF_API_KEY is missing. Cannot generate story.")

    model = "meta-llama/Llama-3.2-1B-Instruct"
    
    prompt = f"""Generate a short, shocking, and 100% TRUE story about {category}. 
Requirements:
1. Start with a massive hook.
2. Tell the story in a fast-paced, engaging way.
3. End with a shocking realization or fact.
4. Keep it under 100 words.
5. Format as JSON ONLY:
{{
  "title": "A short viral title",
  "story": "The full story text..."
}}
"""

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 500,
        "temperature": 0.8
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        try:
            response_json = response.json()
        except Exception as json_err:
            print(f"DEBUG: Story API Failed to parse JSON. Response text: '{response.text}'")
            raise json_err

        output = response_json["choices"][0]["message"]["content"]
        
        # Robust JSON extraction
        start = output.find("{")
        end = output.rfind("}") + 1
        if start == -1 or end == 0:
            print(f"DEBUG: Story No JSON found in output: {output}")
            raise RuntimeError("LLM Story Generation failed to produce valid JSON.")

        json_str = output[start:end].strip()
            
        return json.loads(json_str)
    except Exception as e:
        print(f"❌ Story API failed after all attempts ({e}).")
        raise RuntimeError(f"LLM Story Generation failed: {e}")

    print(f"❌ Story API failed after all attempts.")
    raise RuntimeError(f"LLM Story Generation failed.")

if __name__ == "__main__":
    facts = generate_mixed_facts("science")
    for i, f in enumerate(facts):
        print(f"{i+1}. {f['fact']} (True: {f['truth']})")
