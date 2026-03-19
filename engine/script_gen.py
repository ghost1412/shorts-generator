import os
import requests
import json
import random
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


def get_sub_topic(category):
    """
    Returns a granular sub-topic for a given category to ensure LLM variety.
    """
    sub_topics = {
        "science": ["deep sea biology", "quantum mechanics", "forgotten inventors", "human body anomalies", "microscopic life", "unexpected chemistry", "bizarre psychology experiments"],
        "space": ["exoplanets", "black holes", "moon landing secrets", "stellar phenomena", "alien life theories", "the edge of the universe", "rogue planets"],
        "animals": ["creatures of the abyss", "weird mating rituals", "animal intelligence", "parasites", "extinct monsters", "animal camouflage", "venomous oddities"],
        "history": ["bizarre royal laws", "untold warfare", "lost civilizations", "the middle ages", "secret societies", "forgotten plagues", "ancient technology"],
        "anime_lore": ["hidden easter eggs", "banned episodes", "mangaka secrets", "budget cuts", "pilot episodes differences", "lost media anime", "censorship history"],
        "intimacy_facts": ["historical dating rituals", "psychology of attraction", "weird laws about love", "evolutionary biology", "hormonal secrets", "body language myths"],
        "cooking_hacks": ["molecular gastronomy", "forgotten ancient recipes", "food chemistry", "industrial food secrets", "chef shortcuts", "dangerous ingredients in history"]
    }
    return random.choice(sub_topics.get(category, [category]))

def generate_mixed_facts(category="science"):
    """
    Generates 2 True facts and 1 False fact using LLM with robust fallbacks.
    Returns a dict: {"hook": str, "facts": list}
    """
    url = "https://router.huggingface.co/v1/chat/completions"
    selected_sub = get_sub_topic(category)
    print(f"[Log] Selected sub-topic for variety: {selected_sub}")

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }

    if not HF_API_KEY:
        print("DEBUG: HF_API_KEY is missing!")
        raise RuntimeError("HF_API_KEY is missing. Cannot generate facts.")

    model = "meta-llama/Llama-3.1-8B-Instruct" 
    
    prompt = f"""SPOT THE LIE! 🔍 One of these facts is a fake. Can you find it?
Generate three short, shocking, and OBSCURE facts about {selected_sub}. Exactly two must be true and one must be a believable lie.
REQUIREMENT: Focus on RARE information that most people don't know. Avoid common trivia.

VIRAL HOOK REQUIREMENT:
The start of the video MUST be a high-engagement hook. 
Include a 'hook' field in your JSON response that uses one of these styles:
- "99% of people get this WRONG... Can you spot the lie about {category}?"
- "Only GIGACHADS can find the fake fact here! 😱"
- "One of these {category} facts is a DEADLY LIE. Which one?"

CRITICAL: YOU MUST DOUBLE CHECK YOUR KNOWLEDGE. 
- If a fact is marked as 'true', it must be 100% FACTUALLY ACCURATE and VERIFIABLE.
- Do not invent or exaggerate details for 'true' facts.
- The 'lie' must be believable but clearly false to an expert.

Format as JSON ONLY.
{{
  "hook": "The aggressive viral hook here",
  "facts": [
    {{"fact": "...", "truth": true}},
    {{"fact": "...", "truth": true}},
    {{"fact": "...", "truth": false}}
  ]
}}
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
            
            data = robust_json_parse(output)
            hook = data.get("hook", f"Can you spot the lie about {category}?")
            facts_list = data.get("facts", [])
            
            # VALIDATION: Ensure exactly 2 True and 1 False
            trues = [f for f in facts_list if f.get("truth") is True]
            falses = [f for f in facts_list if f.get("truth") is False]
            
            if len(trues) == 2 and len(falses) == 1:
                for f in facts_list:
                    # Clean any "Fact X: " prefixes generated by the LLM
                    f["fact"] = f["fact"].split(": ", 1)[-1] if ": " in f["fact"] else f["fact"]
                
                # Return the hook and facts separately for cleaner script construction in main.py
                return {"hook": hook, "facts": facts_list[:3]}
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
    selected_sub = get_sub_topic(category)
    print(f"[Log] STORY: Selected sub-topic: {selected_sub}")
    
    prompt = f"""Generate a short, shocking, and 100% TRUE story about {selected_sub}. 
VIRAL REQUIREMENTS:
1. START WITH A MASSIVE CURIOSITY GAP (e.g., "The government doesn't want you to know about this {selected_sub} incident...").
2. USE AGGRESSIVE HOOKS: "99% have no idea this happened," "This will keep you up at night," etc.
3. Focus on an OBSCURE and RARE event. Avoid common stories or well-known events.
4. Tell the story in a fast-paced, engaging way.
4. End on a shocking twist or realization.
5. Keep it under 100 words.

CRITICAL: The story MUST be 100% FACTUALLY ACCURATE and VERIFIABLE. 
Do not hallucinate or embellish details.

Format as JSON ONLY:
{{
  "title": "A short viral title with emojis",
  "story": "The full story text starting with the intense hook..."
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
    selected_sub = get_sub_topic(category)
    print(f"[Log] WYR: Selected sub-topic: {selected_sub}")
    
    prompt = f"""Generate a HILARIOUS and highly engaging "Would you rather" question about {selected_sub}.
REQUIREMENTS:
1. Make it EXTREMELY funny, awkward, or mind-blowing to encourage comments.
2. Focus on OBSCURE scenarios. Avoid common "Would you rather" tropes.
3. Both options must be equally absurd but realistic to the theme.
4. CRITICAL: Ensure the options make sense and are well-phrased.

Format as JSON ONLY:
{{
  "option_a": "Option A relating to {selected_sub}",
  "option_b": "Option B relating to {selected_sub}",
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
    selected_sub = get_sub_topic(category)
    print(f"[Log] REDDIT: Selected sub-topic: {selected_sub}")
    
    prompt = f"""Generate a highly dramatic, controversial, or shocking 1st-person story like you would see on r/AmItheAsshole or r/TrueOffMyChest regarding {selected_sub}. 
Requirements:
1. Start with a hook that clearly states the conflict (e.g., "Am I the jerk for banning my {selected_sub} from my wedding?").
2. Focus on OBSCURE and RARE scenarios. Avoid generic drama.
3. Tell the story in a fast-paced, emotional way.
4. Keep it under 120 words.
5. End on a cliffhanger or a controversial note asking for judgment.
6. Format as JSON ONLY. Escape all double quotes inside the text.
JSON Structure:
{{
  "title": "A short viral title regarding {selected_sub}",
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
    selected_sub = get_sub_topic(category)
    print(f"[Log] TRIVIA: Selected sub-topic: {selected_sub}")
    
    prompt = f"""Generate a difficult but fun trivia question about {selected_sub}.
REQUIREMENTS:
1. Provide one challenging, OBSCURE question. Avoid common trivia.
2. Provide exactly three short options (A, B, and C).
3. State the correct option letter (A, B, or C).
4. CRITICAL: The question and answer MUST be 100% FACTUALLY ACCURATE and VERIFIABLE.

Format as JSON ONLY:
{{
  "question": "A challenging question about {category}",
  "opt_a": "Option A",
  "opt_b": "Option B",
  "opt_c": "Option C",
  "answer": "Correct Option Text"
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
    selected_sub = get_sub_topic(category)
    print(f"[Log] QUOTE: Selected sub-topic: {selected_sub}")
    
    prompt = f"""Generate a profound, highly emotional or stoic quote about {selected_sub}.
Requirements:
1. Focus on an OBSCURE but powerful perspective.
1. Provide the quote text (around 10-25 words).
2. Provide the author's name (can be a real historical figure or "Unknown").
3. Make it incredibly cinematic and thought-provoking.
4. Format as JSON ONLY. Escape all double quotes inside the text.
JSON Structure:
{{
  "quote": "Profound quote text about {category}",
  "author": "Author Name"
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
