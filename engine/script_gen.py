import os
import requests
import json
from dotenv import load_dotenv

import re
load_dotenv()

HF_API_KEY = os.getenv("HF_API_KEY")

def robust_json_parse(output):
    """
    Tries to extract and fix a JSON block from LLM output.
    Handles unescaped newlines, control characters, and common LLM quirks.
    """
    # Remove control characters that break JSON (except for newline/tab/carriage-return)
    clean_output = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', output)
    
    # Try to find the inner JSON block (starts with { or [ and ends with } or ])
    match = re.search(r'([\[\{].*[\]\}])', clean_output, re.DOTALL)
    if not match:
        raise ValueError("No JSON-like structure found in response.")
        
    json_str = match.group(1).strip()
    
    # Common fixes for LLM-generated JSON
    # 1. Unescaped newlines inside strings
    def fix_newlines(m):
        return m.group(0).replace('\n', '\\n')
    json_str = re.sub(r'"[^"]*?"', fix_newlines, json_str, flags=re.DOTALL)
    
    # 2. Fix trailing commas (e.g. [1, 2, ])
    json_str = re.sub(r',\s*([\]\}])', r'\1', json_str)
    
    return json.loads(json_str)


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

    model = "meta-llama/Llama-3.1-8B-Instruct" 
    
    prompt = f"""SPOT THE LIE! 🔍 One of these facts is a fake. Can you find it?
Generate three short, shocking facts about {category}. Exactly two must be true and one must be a believable lie.

CRITICAL: YOU MUST DOUBLE CHECK YOUR KNOWLEDGE. 
- If a fact is marked as 'true', it must be 100% FACTUALLY ACCURATE and VERIFIABLE.
- If it relates to anime/media lore, ensure the plot points are actually in the source material.
- If it relates to science, it must be the current scientific consensus.
- The lie must be believable but objectively false.

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
            "max_tokens": 800,
            "temperature": 0.1 + (attempt * 0.2)
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
            
            facts = robust_json_parse(output)
            
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

    model = "meta-llama/Llama-3.1-8B-Instruct"
    
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
        
        return robust_json_parse(output)
    except Exception as e:
        print(f"❌ Story API failed after all attempts ({e}).")
        raise RuntimeError(f"LLM Story Generation failed: {e}")

    print(f"❌ Story API failed after all attempts.")
    raise RuntimeError(f"LLM Story Generation failed.")

def generate_wyr(category="general"):
    """
    Generates a 'Would You Rather' scenario with fake percentages.
    Returns: {"option_a": str, "option_b": str, "percent_a": int, "percent_b": int}
    """
    url = "https://router.huggingface.co/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }

    if not HF_API_KEY:
        print("DEBUG: HF_API_KEY is missing for WYR!")
        raise RuntimeError("HF_API_KEY is missing. Cannot generate WYR.")

    model = "meta-llama/Llama-3.1-8B-Instruct"
    
    prompt = f"""Generate a HILARIOUS, highly social-media-engaging "Would you rather" question for a YouTube Shorts audience. The topic is {category}.
Requirements:
1. Make it EXTREMELY funny or awkward — the kind of question that makes people immediately want to comment their answer.
2. Both options should be equally terrible or absurd in a funny way (classic WYR style). 
3. Examples of great formats:
  - "Sneeze glitter for the rest of your life" vs "Hiccup a fart sound every time you laugh"
  - "Your loud chewing partner gets promoted above you" vs "Your most embarrassing memory plays on the TV at your wedding"
4. Keep each option under 20 words.
5. No percentages needed. Just the two options.
6. Format as JSON ONLY. Escape all double quotes inside the text.
JSON Structure:
{{
  "option_a": "Option A text here",
  "option_b": "Option B text here",
  "percent_a": 50,
  "percent_b": 50
}}
"""

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 400,
        "temperature": 0.85
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        response_json = response.json()
        output = response_json["choices"][0]["message"]["content"]
        
        wyr = robust_json_parse(output)
        
        # Validation
        if "option_a" in wyr and "option_b" in wyr and "percent_a" in wyr and "percent_b" in wyr:
             if wyr["percent_a"] + wyr["percent_b"] != 100:
                  # Fix it if math is wrong
                  wyr["percent_b"] = 100 - wyr["percent_a"]
             return wyr
        else:
            raise ValueError("Missing keys in JSON")
            
    except Exception as e:
        print(f"❌ WYR API failed: {e}")
        raise RuntimeError(f"LLM WYR Generation failed after all attempts: {e}")

def generate_reddit_story(category="general"):
    """
    Generates a dramatic, first-person Reddit-style story (e.g. AITA).
    Returns: {"title": str, "story": str}
    """
    url = "https://router.huggingface.co/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }

    if not HF_API_KEY:
        print("DEBUG: HF_API_KEY is missing for REDDIT!")
        raise RuntimeError("HF_API_KEY is missing. Cannot generate REDDIT story.")

    model = "meta-llama/Llama-3.1-8B-Instruct"
    
    prompt = f"""Generate a highly dramatic, controversial, or shocking 1st-person story like you would see on r/AmItheAsshole or r/TrueOffMyChest regarding {category}. 
Requirements:
1. Start with a hook that clearly states the conflict (e.g., "Am I the jerk for kicking my sister out of my wedding?").
2. Tell the story in a fast-paced, emotional way.
3. Keep it under 120 words.
4. End on a cliffhanger or a controversial note asking for judgment.
5. Format as JSON ONLY. Escape all double quotes inside the text.
JSON Structure:
{{
  "title": "A short viral title",
  "story": "The full story text..."
}}
"""

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 600,
        "temperature": 0.85
    }

    # Try up to 2 times
    for attempt in range(2):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=25)
            response.raise_for_status()
            output = response.json()["choices"][0]["message"]["content"]
            
            return robust_json_parse(output)
        except Exception as e:
            print(f"[Warning] Reddit attempt {attempt+1} failed ({type(e).__name__}: {e})")
            continue

    print(f"❌ REDDIT API failed after retries.")
    raise RuntimeError("LLM REDDIT Generation failed to produce valid JSON after retries.")

def generate_trivia(category="general knowledge"):
    """
    Generates a Trivia question with 3 options and the correct answer index.
    Returns: {"question": str, "opt_a": str, "opt_b": str, "opt_c": str, "answer": str}
    """
    url = "https://router.huggingface.co/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }

    if not HF_API_KEY:
        print("DEBUG: HF_API_KEY is missing for TRIVIA!")
        raise RuntimeError("HF_API_KEY is missing. Cannot generate TRIVIA.")

    model = "meta-llama/Llama-3.1-8B-Instruct"
    
    prompt = f"""Generate a difficult but fun trivia question about {category}.
Requirements:
1. Provide the question.
2. Provide exactly three short options (A, B, and C).
3. State the correct option letter (A, B, or C).
4. Format as JSON ONLY:
{{
  "question": "What is the capital of Australia?",
  "opt_a": "Sydney",
  "opt_b": "Melbourne",
  "opt_c": "Canberra",
  "answer": "C"
}}
"""

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 400,
        "temperature": 0.7
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        response_json = response.json()
        output = response_json["choices"][0]["message"]["content"]
        
        return robust_json_parse(output)
    except Exception as e:
        print(f"❌ TRIVIA API failed: {e}")
        raise RuntimeError(f"LLM TRIVIA Generation failed after all attempts: {e}")

def generate_quote(category="stoic"):
    """
    Generates a deep, motivational, or philosophical quote.
    Returns: {"quote": str, "author": str}
    """
    url = "https://router.huggingface.co/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }

    if not HF_API_KEY:
        print("DEBUG: HF_API_KEY is missing for QUOTE!")
        raise RuntimeError("HF_API_KEY is missing. Cannot generate QUOTE.")

    model = "meta-llama/Llama-3.1-8B-Instruct"
    
    prompt = f"""Generate a profound, highly emotional or stoic quote about {category}.
Requirements:
1. Provide the quote text (around 10-25 words).
2. Provide the author's name (can be a real historical figure or "Unknown").
3. Make it incredibly cinematic and thought-provoking.
4. Format as JSON ONLY. Escape all double quotes inside the text.
JSON Structure:
{{
  "quote": "The only way to achieve the impossible is to believe it is possible.",
  "author": "Charles Kingsleigh"
}}
"""

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 400,
        "temperature": 0.8
    }

    for attempt in range(2):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            response.raise_for_status()
            output = response.json()["choices"][0]["message"]["content"]
            
            return robust_json_parse(output)
        except Exception as e:
            print(f"[Warning] Quote attempt {attempt+1} failed: {e}")
            continue

    print(f"❌ QUOTE API failed after retries.")
    raise RuntimeError("LLM QUOTE Generation failed to produce valid JSON after retries.")

if __name__ == "__main__":
    facts = generate_mixed_facts("science")
    for i, f in enumerate(facts):
        print(f"{i+1}. {f['fact']} (True: {f['truth']})")
