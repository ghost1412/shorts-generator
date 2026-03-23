import os
import requests
import json
import random
from dotenv import load_dotenv

import re
load_dotenv()

HF_API_KEY = os.getenv("HF_API_KEY")
LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:11434/api/chat") # Default Ollama

def get_llm_response(
    prompt,
    system_prompt="You are a viral YouTube shorts creator. ALWAYS respond with raw JSON only. No conversational text.",
    max_tokens=2048,
    temperature=0.3,
    model="meta-llama/Llama-3.1-8B-Instruct"
):
    import requests

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    # 1. Try Local LLM (Ollama)
    if LOCAL_LLM_URL:
        try:
            print(f"[Log] Attempting local LLM at {LOCAL_LLM_URL}...")

            payload = {
                "model": "llama3:8b-instruct-q4_K_M",  # 🔥 better model
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": min(max_tokens, 32768), # Allow longer responses for complex extractions
                    "num_ctx": 32768  # 🔥 Massive context for 100k+ char transcripts
                }
            }

            response = requests.post(
                LOCAL_LLM_URL,
                json=payload,
                timeout=300  # 🔥 increased for long videos
            )
            response.raise_for_status()

            try:
                data = response.json()
                content = data.get("message", {}).get("content", "")
                if not content:
                    raise json.JSONDecodeError("Empty content in main object", "", 0)
            except json.JSONDecodeError as e:
                # 🟢 PHASE 13: Robust NDJSON/Extra Data Stitching
                lines = response.text.strip().split('\n')
                all_content = []
                for line in lines:
                    try:
                        temp = json.loads(line)
                        c = temp.get("message", {}).get("content", "")
                        if c: all_content.append(c)
                    except:
                        continue
                if all_content:
                    content = "".join(all_content)
                    data = {"message": {"content": content}}
                else:
                    raise e

            content = data["message"]["content"]  # ✅ guaranteed non-empty
            print("[Log] Local LLM success!")
            return content

        except requests.exceptions.Timeout:
            print("[Warn] Local LLM timeout, retrying with extra time...")
            try:
                response = requests.post(
                    LOCAL_LLM_URL,
                    json=payload,
                    timeout=300 # 5 minutes for massive transcripts
                )
                response.raise_for_status()
                
                try:
                    data = response.json()
                    content = data.get("message", {}).get("content", "")
                    if not content:
                        raise json.JSONDecodeError("Empty content in main object (retry)", "", 0)
                except json.JSONDecodeError as e:
                    # 🟢 PHASE 13: Robust NDJSON/Extra Data Stitching (Retry)
                    lines = response.text.strip().split('\n')
                    all_content = []
                    for line in lines:
                        try:
                            temp = json.loads(line)
                            c = temp.get("message", {}).get("content", "")
                            if c: all_content.append(c)
                        except:
                            continue
                    if all_content:
                        content = "".join(all_content)
                        data = {"message": {"content": content}}
                    else:
                        raise e
                        
                return data["message"]["content"]
            except Exception as e:
                print(f"[Info] Retry failed: {e}")

        except Exception as e:
            print(f"[Info] Local LLM failed: {e}")
            # Ensure we don't leave connection hanging
            if 'response' in locals() and hasattr(response, 'close'):
                response.close()

    # 2. HuggingFace fallback
    url = "https://router.huggingface.co/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature
    }

    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def _clean_json_string(s):
    """Internal helper to clean comments and trailing commas."""
    import re
    # 1. Remove control characters
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', s)
    # 2. Fix unescaped newlines inside strings
    def fix_newlines(m):
        return m.group(0).replace('\n', '\\n')
    s = re.sub(r'"[^"]*?"', fix_newlines, s, flags=re.DOTALL)
    # 3. Strip comments
    s = re.sub(r'//.*?\n', '', s)
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.DOTALL)
    # 4. Fix trailing commas (e.g. [1, 2, ])
    s = re.sub(r',\s*([\]\}])', r'\1', s)
    return s.strip()

def robust_json_parse(output):
    """Tries multiple strategies to extract JSON from LLM output, including regex fallback."""
    import re, json
    if not output: return None
        
    # 🟢 PHASE 20: REGEX FALLBACK (for conversational LLMs)
    # Extracts patterns like (0.00s - 15.4s) or "start": 10.5, "end": 20.1
    def try_regex_recovery(text):
        print("[Log] JSON parse failed, attempting Regex recovery from conversational text...")
        # Patterns: (10.5s - 20.1s), 10.5-20.1, [10.5, 20.1], 01:23 - 01:45
        patterns = [
            r"(\d+\.?\d*)\s*s?\s*[\-\–\—to,:]+\s*(\d+\.?\d*)\s*s?", # 10.5s - 20.1s
            r"(\d{1,2}:\d{2}:?\d{0,2})\s*[\-\–\—to,]+\s*(\d{1,2}:\d{2}:?\d{0,2})", # 01:23 - 01:45
            r"start[\"':\s]+(\d+\.?\d*)[\s,]*end[\"':\s]+(\d+\.?\d*)", # "start": 10.5
        ]
        
        def time_to_sec(ts):
            if ":" not in ts: return float(ts)
            parts = ts.split(":")
            if len(parts) == 3: return int(parts[0])*3600 + int(parts[1])*60 + float(parts[2])
            return int(parts[0])*60 + float(parts[1])

        items = []
        for p in patterns:
            matches = re.findall(p, text, re.IGNORECASE)
            for m in matches:
                try:
                    s_val = time_to_sec(m[0])
                    e_val = time_to_sec(m[1])
                    if e_val > s_val:
                        if not any(i['start'] == s_val and i['end'] == e_val for i in items):
                            items.append({"start": s_val, "end": e_val, "reason": "Recovered Segment", "viral_score": 80})
                except: continue
            if items: break
        return items if items else None

    start_idx = -1
    for i, char in enumerate(output):
        if char in ('{', '['):
            start_idx = i
            break
            
    if start_idx == -1:
        # 🟢 Fallback to Regex if NO JSON structure at all
        recovered = try_regex_recovery(output)
        if recovered: return recovered
        print(f"[Error] No JSON start found in output: {output[:300]}...")
        return None
        
    # Manual scan to find the first complete balanced structure
    stack = []
    in_string = False
    escaped = False
    balanced_str = ""
    
    for i in range(start_idx, len(output)):
        char = output[i]
        if char == '"' and not escaped: in_string = not in_string
        if in_string:
            if char == '\\': escaped = not escaped
            else: escaped = False
        else:
            if char == '{': stack.append('}')
            elif char == '[': stack.append(']')
            elif char in ('}', ']'):
                if stack and stack[-1] == char:
                    stack.pop()
                    if not stack: 
                        balanced_str = output[start_idx:i+1]
                        break
    
    json_str = _clean_json_string(balanced_str or output[start_idx:])
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as initial_err:
        # 1. Handle "Extra data" (take the first object only)
        if "Extra data" in str(initial_err):
            try:
                surgical_str = _clean_json_string(json_str[:initial_err.pos])
                return json.loads(surgical_str)
            except:
                pass 
                
        print(f"[Log] Initial JSON parse failed ({initial_err}), attempting auto-repair...")
        
        # 2. Stack-based repair for truncated structures
        stack = []
        in_string = False
        escaped = False
        for char in json_str:
            if char == '"' and not escaped: in_string = not in_string
            if in_string:
                if char == '\\': escaped = not escaped
                else: escaped = False
                continue
            if char == '{': stack.append('}')
            elif char == '[': stack.append(']')
            elif char in ('}', ']'):
                if stack and stack[-1] == char: stack.pop()
        
        if stack:
            repaired_str = json_str.strip()
            
            # Use rfind to see if we ended in the middle of an object
            last_valid_end = max(repaired_str.rfind('}'), repaired_str.rfind(']'))
            if last_valid_end != -1 and last_valid_end < len(repaired_str) - 2:
                junk = repaired_str[last_valid_end+1:].strip()
                if junk and (junk.startswith(',') or junk.startswith('{')):
                    print(f"[Log] Discarding partial trailing junk: {junk[:20]}...")
                    repaired_str = repaired_str[:last_valid_end+1]
                    # Recursive call on cleaned string
                    return robust_json_parse(repaired_str)

            repaired_str = _clean_json_string(repaired_str + "".join(reversed(stack)))
            
            try:
                return json.loads(repaired_str)
            except Exception as repair_err:
                print(f"[Error] Auto-repair failed at {getattr(repair_err, 'pos', '?')}: {repair_err}")
                print(f"[Log] Repaired snippet (hex): {' '.join([f'{ord(c):02x}' for c in repaired_str[:20]])}")
                print(f"[Log] Repaired snippet (text): {repaired_str[:50]}...")
                raise initial_err
        else:
            print(f"[Log] Original failing snippet (hex): {' '.join([f'{ord(c):02x}' for c in json_str[:20]])}")
            print(f"[Error] No stack mismatch found, cannot repair: {initial_err}")
            raise initial_err

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

def validate_semantics(facts):
    """
    Ensures:
    - Exactly 2 true, 1 false
    - False fact differs by ONLY one detail
    """
    if not facts or len(facts) != 3:
        return False

    truths = [f for f in facts if f.get("truth") is True]
    falses = [f for f in facts if f.get("truth") is False]

    if len(truths) != 2 or len(falses) != 1:
        return False

    # Heuristic: false fact should be very similar to one true fact
    false_fact = falses[0]["fact"]

    similarity_hits = 0
    for t in truths:
        # crude similarity check
        common_words = set(false_fact.split()) & set(t["fact"].split())
        if len(common_words) >= 3:
            similarity_hits += 1

    return similarity_hits >= 1

def reject_bad_facts(facts):
    """Filters out vague or generic facts."""
    if not facts: return True
    for f in facts:
        fact = f["fact"].lower()
        # reject vague facts
        if len(fact.split()) < 4:
            return True
        # reject generic patterns
        if any(v in fact for v in ["some", "many", "most people"]):
            return True
    return False

def reject_duplicates(facts):
    """Rejects facts that are structurally or semantically too similar."""
    seen = set()
    for f in facts:
        key = f["fact"].lower()
        # normalize (remove numbers + punctuation)
        key = re.sub(r'[^a-z ]', '', key)
        # Check first 6 words for duplication (structural repetition)
        key_start = " ".join(key.split()[:6])
        if key_start in seen:
            return True
        seen.add(key_start)
    return False

def reject_same_subject(facts):
    """Ensures each fact is about a DIFFERENT person/entity."""
    subjects = []
    stopwords = ["the", "a", "an", "this", "that"]
    for f in facts:
        words = [w.lower() for w in f["fact"].split() if w.lower() not in stopwords]
        if len(words) >= 2:
            # Check first 2 meaningful words
            subjects.append(" ".join(words[:2]))
    
    # We need as many unique subjects as there are facts
    return len(set(subjects)) < len(facts)

def check_hallucinations(facts):
    """
    Uses a second LLM call to act as a skeptic/fact-checker.
    Ensures 'True' facts aren't actually hallucinations or logically impossible.
    """
    if not facts: return False
    
    # Prepare a condensed list for the checker
    test_str = "\n".join([f"- {f['fact']}" for f in facts if f['truth']])
    
    prompt = f"""You are an elite Fact-Checker. Review these {len(facts)} facts. 
Are ANY of them actually FALSE, logically impossible, or based on common myths?

FACTS TO CHECK:
{test_str}

CRITICAL CHECKS:
1. Movies DON'T have 'pilots' (only TV shows).
2. People can't use tech that wasn't invented yet.
3. No 'Einstein failed math' type myths.
4. No 'produced in X but aired in Y' ambiguous confusing facts.

First, briefly explain your reasoning in 1-2 sentences.
Then, on a new line, write exactly 'DECISION: PASS' if ALL facts in the list are verified and logically sound.
Write exactly 'DECISION: FAIL' if ANY fact is suspicious, incorrect, or ambiguous.
"""

    try:
        response_text = get_llm_response(prompt, temperature=0.0, max_tokens=150)
        output = response_text.strip().upper()
        
        # Log the output safely on one line
        log_out = output.replace('\n', ' | ')
        print(f"[Log] AI Fact-Checker Output: {log_out}")
        
        # ROBUST CHECK: Look for 'DECISION: PASS'
        return "DECISION: PASS" not in output
    except Exception as e:
        print(f"[Warning] AI Fact-Checker failed ({e}). Defaulting to safety.")
        # If checker fails, we reject just in case
        return True

def mutate_year(text):
    """Subtle year shift (+/- 1-2 years)."""
    return re.sub(r'\d{4}', lambda m: str(int(m.group()) + random.choice([-1, 1, 2])), text)

def mutate_location(text):
    """Subtle location swap for realism."""
    locations = ["France", "Germany", "USA", "Japan", "Italy", "London", "Paris", "Berlin"]
    for loc in locations:
        if loc in text:
            new_loc = random.choice([l for l in locations if l != loc])
            return text.replace(loc, new_loc)
    return text

def mutate_number(text):
    """Subtle number shift for stats/counts (ensuring positive values)."""
    return re.sub(r'\b\d+\b', lambda m: str(max(1, int(m.group()) + random.choice([-1, 1, 3]))), text)

def mutate_relationship(text):
    """Semantic pivot for high-quality lies."""
    pairs = {"brother": "father", "father": "brother", "wife": "sister", "son": "friend", "rival": "mentor"}
    for k, v in pairs.items():
        if k in text.lower():
            return re.sub(re.escape(k), v, text, flags=re.IGNORECASE)
    return text

def mutate_method(text):
    """Mutation of mechanism/tool."""
    pairs = {"using": "without", "with": "without", "by": "without"}
    for k, v in pairs.items():
        if k in text.lower():
            return re.sub(re.escape(k), v, text, flags=re.IGNORECASE)
    return text

def create_false_from_true(base_text):
    """Procedurally generates a SUBTLE lie using weighted mutation types."""
    base = base_text
    
    mutations = [
        mutate_year,
        mutate_location,
        mutate_number,
        mutate_relationship,
        mutate_method
    ]
    
    # Try mutations in random order until one actually changes the text
    for m in random.sample(mutations, len(mutations)):
        new_fact = m(base)
        if new_fact != base:
            return new_fact

    # Final robust fallback if no pattern matched
    return base.rstrip(".") + " in a different year"
def reject_vague_facts(facts):
    """Rejects facts that are 'partially true' or confusing (e.g. produced in x but released in y)."""
    banned_keywords = ["produced in", "recorded in", "but not", "originally", "later aired"]
    for f in facts:
        text = f["fact"].lower()
        if any(b in text for b in banned_keywords):
            return True
    return False

def validate_story(data):
    """Ensures story is verifiable and not vague."""
    story = data.get("story", "").lower()
    if not story: return False
    # must contain anchor (digit/year/number)
    if not any(char.isdigit() for char in story):
        return False
    # must not be vague
    vague_words = ["someone", "somewhere", "many people"]
    if any(v in story for v in vague_words):
        return False
    return True

def validate_wyr(data):
    """Ensures WYR options are unique and balanced."""
    a = data.get("option_a", "")
    b = data.get("option_b", "")
    if not a or not b or a == b:
        return False
    # must be different enough (heuristic)
    if len(set(a.split()) & set(b.split())) > 5:
        return False
    return True

def validate_trivia(data):
    """Ensures trivia has unique options and correct answer mapping."""
    opts = [data.get("opt_a"), data.get("opt_b"), data.get("opt_c")]
    if not all(opts) or len(set(opts)) != 3:
        return False
    # answer must match one option exactly
    if data.get("answer") not in opts:
        return False
    return True

def validate_reddit(data):
    """Ensures Reddit story has tension and a question for judgment."""
    story = data.get("story", "").lower()
    if not story: return False
    if "?" not in story:
        return False
    if not any(x in story for x in ["am i", "was i", "should i"]):
        return False
    return True

def validate_quote(data):
    """Ensures quote has sufficient depth and isn't a cliché."""
    quote = data.get("quote", "")
    if not quote or len(quote.split()) < 8:
        return False
    banned = ["believe in yourself", "never give up", "follow your dreams"]
    if any(b in quote.lower() for b in banned):
        return False
    return True

def validate_news(data):
    """Ensures news story isn't vague and has minimum factual substance."""
    story = data.get("story", "").lower()
    if not story: return False
    # must not hallucinate vague stuff
    vague_sources = ["some reports", "many believe", "sources say", "it is said"]
    if any(x in story for x in vague_sources):
        return False
    # must have entity/substance (basic heuristic: > 8 words)
    if len(story.split()) < 8:
        return False
    return True

def validate_sound_challenge(data):
    """Ensures the object and sound prompt are present."""
    return bool(data.get("object") and data.get("sound_query"))

def with_best_of_n(func, validator, n=3, fallback=None):
    """
    Runs an LLM generator n times, filters for valid results,
    and returns the one with the highest 'viral score'.
    Fulfills both Quality (Best of N) and Validity (Retry) needs in one pass.
    """
    results = []
    for i in range(n):
        try:
            res = func(i)
            if validator(res):
                results.append(res)
        except Exception as e:
            print(f"⚠️ Attempt {i+1} failed ({type(e).__name__}): {e}")
            
    if not results:
        if fallback:
            print("🚨 All attempts failed or invalid. Using fallback.")
            return fallback()
        raise RuntimeError("LLM generation failed validation after all attempts.")
        
    def score(x):
        text = str(x)
        # Higher score for longer text (substance) + extra points for punchy punctuation
        return len(text) + 12 * text.count("!") + 8 * text.count("?")
    
    best = max(results, key=score)
    print(f"[Log] Best of {len(results)} valid results selected (Score: {score(best)})")
    return best

# Removed redundant generate_best_of_3 function as it's now integrated into with_best_of_n

def generate_fallback_facts(category):
    """Safely returns hardcoded obscure facts if LLM fails."""
    return {
        "hook": "Spot the lie instantly 🔍",
        "facts": [
            {"fact": "First webcam watched coffee pot", "truth": True},
            {"fact": "IBM Simon debuted in 1992", "truth": True},
            {"fact": "First mouse invented in 1980", "truth": False}
        ]
    }

def generate_long_form_facts(category="science", count=12):
    """
    Generates a large set of true facts for long-form landscape videos.
    Returns a dict: {"title": str, "facts": list}
    """
    url = "https://router.huggingface.co/v1/chat/completions"
    selected_sub = get_sub_topic(category)
    print(f"[Log] [Long-Form] Selected sub-topic: {selected_sub}")

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""Generate a high-impact, epic list of {count} fascinating facts about {selected_sub}.
    
    TONE: Epic, high-stakes, world-shaking.
    
    RULES:
    1. Each fact must be extremely punchy (under 12 words).
    2. Include specific dates, names, or massive numbers.
    3. Ensure 100% accuracy.
    4. Provide a viral 'Epic Title' for the video.

    OUTPUT FORMAT (JSON ONLY):
    {{
      "title": "Epic catchy title",
      "facts": [
        {{"fact": "...", "truth": true}},
        ... ({count} total)
      ]
    }}
    """
    
    try:
        response_text = get_llm_response(prompt, temperature=0.7, max_tokens=1200)
        data = robust_json_parse(response_text)
        
        # Basic validation: ensure we have at least 8 facts
        if len(data.get("facts", [])) < 8:
            raise ValueError("Insufficient facts generated.")
            
        print(f"[Log] Successfully generated {len(data['facts'])} long-form facts.")
        return data
    except Exception as e:
        print(f"[Error] Long-form fact generation failed: {e}")
        # Fallback to a few facts
        return {
            "title": f"The Secrets of {selected_sub.capitalize()}",
            "facts": [{"fact": "The universe is expanding faster than light.", "truth": True}] * count
        }

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
    
    prompt = f"""SPOT THE LIE! 🔍 Review these facts about {selected_sub}. 
    
TASK:
Generate EXACTLY 3 TRUE facts ONLY. 
DO NOT generate any false facts. 

VIRAL RETENTION RULES:
1. Use a MASSIVE curiosity hook. Avoid clichés.
2. The Hook MUST be an incomplete thought that the facts satisfy.
3. The script MUST end with a "Loop Lead" that connects back to the hook perfectly.

STRICT RULES (MUST FOLLOW):
1. Each fact must be under 10 words.
2. Facts must be specific (include year, name, or detail).
3. NO fictional or hybrid show names.
4. NO technical-sounding jargon or web URLs.

CRITICAL DIVERSITY RULES:
- Each fact MUST be about a DIFFERENT person, place, or entity.
- Be 100% CERTAIN of the TRUE facts. 

OUTPUT FORMAT (JSON ONLY):
{{
  "hook": "Aggressive curiosity-gap hook",
  "facts": [
    {{"fact": "...", "truth": true}},
    {{"fact": "...", "truth": true}},
    {{"fact": "...", "truth": true}}
  ],
  "loop_lead": "Short bridge that leads back to the hook"
}}
"""
    
    def llm_call(attempt):
        response_text = get_llm_response(prompt, temperature=0.2, max_tokens=800)
        data = robust_json_parse(response_text)
        
        # Clean data (prefixes)
        facts_list = data.get("facts", [])
        for f in facts_list:
            f["fact"] = f["fact"].split(": ", 1)[-1] if ": " in f["fact"] else f["fact"]
        data["facts"] = facts_list[:3] # We only need 3 true ones
        return data

    def facts_validator(data):
        facts = data.get("facts", [])
        if len(facts) < 3: 
            print("❌ Validation failed: Not enough facts.")
            return False
        if reject_bad_facts(facts):
            print("❌ Validation failed: Bad facts/formatting.")
            return False
        if reject_duplicates(facts):
            print("❌ Validation failed: Duplicates detected.")
            return False
        if reject_same_subject(facts):
            print("❌ Validation failed: Same subject repeated.")
            return False
        if check_hallucinations(facts): # NEW: Dynamic AI Fact-Checker on TRUE facts
            print("❌ Validation failed: AI Hallucination detected.")
            return False
        return True

    result = with_best_of_n(
        llm_call, 
        facts_validator, 
        n=3,
        fallback=lambda: generate_fallback_facts(category)
    )
    
    # ASSEMBLY: 3 Unique True Subjects -> 2 True + 1 Procedural False
    true_facts = [f for f in result["facts"] if f.get("truth") is True]
    
    # Ensure we actually got 3 true facts, if not, fallback
    if len(true_facts) < 3:
        true_facts = generate_fallback_facts(category)["facts"]
        
    kept_true = true_facts[:2]
    fact_to_mutate = true_facts[2]["fact"]
    
    # Generate the lie from the 3rd true fact (Procedural Mutation)
    false_fact_text = create_false_from_true(fact_to_mutate)
    false_fact = {"fact": false_fact_text, "truth": False}
    
    final_facts = kept_true + [false_fact]
    random.shuffle(final_facts)
    
    return {
        "hook": result["hook"],
        "loop_lead": result.get("loop_lead", ""),
        "facts": final_facts
    }

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
VIRAL RETENTION RULES:
1. START WITH A SHOCKING STATEMENT (e.g., "This man shouldn't be alive...").
2. USE AGGRESSIVE HOOKS: "99% have no idea," "The government hid this," etc.
3. FOCUS on the "Forbidden" or "Obscure" detail.
4. The END of the story must bridge perfectly back to the first word of the hook (Seamless Loop).

STORY RULES:
1. Fast-paced, intense delivery.
2. Must include ONE verifiable anchor (year/person/place).
3. Under 90 words.
4. NO TECHNICAL NOISE or "v1.0" or JSON keys.

Format as JSON ONLY:
{{
  "title": "Viral Clickbait Title",
  "story": "Intense story text...",
  "loop_lead": "Optional bridge text for the loop"
}}
"""

    def llm_call(attempt):
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500,
            "temperature": 0.2
        }
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        output = response.json()["choices"][0]["message"]["content"]
        return robust_json_parse(output)

    return with_best_of_n(llm_call, validate_story, n=3)

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
5. NO TECHNICAL NOISE: Do NOT include URLs, version numbers (e.g., v1.0), or "random script things" like JSON keys.

CRITICAL VALIDATION:
- Options must be equally painful or absurd.
- Must force hesitation (user cannot easily choose).
- Avoid obvious better choice.

Format as JSON ONLY:
{{
  "option_a": "Option A relating to {selected_sub}",
  "option_b": "Option B relating to {selected_sub}",
  "percent_a": 50,
  "percent_b": 50
}}
"""

    def llm_call(attempt):
        response_text = get_llm_response(prompt, temperature=0.2, max_tokens=400)
        wyr = robust_json_parse(response_text)
        if wyr.get("percent_a", 0) + wyr.get("percent_b", 0) != 100:
            wyr["percent_b"] = 100 - wyr.get("percent_a", 50)
        return wyr

    return with_best_of_n(llm_call, validate_wyr, n=3)

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
6. NO TECHNICAL NOISE: Do NOT include URLs, version numbers (e.g., v1.0), or "random script things" like JSON keys.
7. Format as JSON ONLY. Escape all double quotes inside the text.

CRITICAL VALIDATION:
- Must include a clear moral dilemma.
- Reader should be unsure who is right.
- Must end with a direct question for judgment (e.g., "Am I the jerk?").

JSON Structure:
{{
  "title": "A short viral title regarding {selected_sub}",
  "story": "The full story text..."
}}
"""

    def llm_call(attempt):
        response_text = get_llm_response(prompt, temperature=0.2, max_tokens=600)
        return robust_json_parse(response_text)

    return with_best_of_n(llm_call, validate_reddit, n=3)

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
3. State the correct option letter (must match exactly one option text).
4. CRITICAL: The question and answer MUST be 100% FACTUALLY ACCURATE and VERIFIABLE.
5. NO TECHNICAL NOISE: Do NOT include URLs, version numbers (e.g., v1.0), or "random script things" like JSON keys.

CRITICAL VALIDATION:
- All options must be unique and plausible.
- Answer MUST match one of the options exactly.

Format as JSON ONLY:
{{
  "question": "A challenging question about {category}",
  "opt_a": "Option A",
  "opt_b": "Option B",
  "opt_c": "Option C",
  "answer": "Correct Option Text"
}}
"""

    def llm_call(attempt):
        response_text = get_llm_response(prompt, temperature=0.2, max_tokens=400)
        return robust_json_parse(response_text)

    return with_best_of_n(llm_call, validate_trivia, n=3)

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
2. Provide the quote text (around 10-25 words).
3. Provide the author's name (can be a real historical figure or "Unknown").
4. Make it incredibly cinematic and thought-provoking.
5. NO TECHNICAL NOISE: Do NOT include URLs, version numbers (e.g., v1.0), or "random script things" like JSON keys.

CRITICAL VALIDATION:
- Quote must be at least 10 words long for depth.
- AVOID cliches (e.g., "believe in yourself", "never give up").
- Must be cinematic and soul-stirring.

6. Format as JSON ONLY. Escape all double quotes inside the text.
JSON Structure:
{{
  "quote": "Profound quote text about {category}",
  "author": "Author Name"
}}
"""

    def llm_call(attempt):
        response_text = get_llm_response(prompt, temperature=0.2, max_tokens=400)
        return robust_json_parse(response_text)

    return with_best_of_n(llm_call, validate_quote, n=3)
def generate_funny_news(category="general", tone="funny"):
    """
    Fetches REAL news from RSS feeds, then uses LLM to rewrite in the chosen tone.
    tone: "funny" = bizarre/sarcastic, "serious" = dramatic/informative
    Returns: {"title": str, "hook": str, "story": str, "source": str, "search_term": str, "tone": str}
    """
    import xml.etree.ElementTree as ET
    import email.utils
    from datetime import datetime, timedelta, timezone

    # --- STEP 1: Fetch real news from RSS feeds based on tone and category ---
    category_queries = {
        "world": "world news international",
        "politics": "politics world politics election",
        "celebrities": "celebrities entertainment pop culture hollywood",
        "tech": "technology ai gadgets tech news",
        "sports": "sports world sports results",
        "business": "business finance economy stock market",
        "science": "science research scientific discovery"
    }
    
    query = category_queries.get(category, f"{category} news")
    
    # --- Define category-specific subreddits ---
    category_subreddits = {
        "celebrities": ["entertainment", "popculture", "celebrities"],
        "tech": ["technology", "programming", "gadgets"],
        "sports": ["sports", "nba", "soccer"],
        "politics": ["politics"],
        "world": ["worldnews"],
        "science": ["science", "space"],
        "business": ["business", "economy"]
    }

    # 1. Base Google News RSS (Highly specific search)
    google_search_suffix = "weird bizarre funny" if tone == "funny" else "latest breaking"
    rss_feeds = [
        f"https://news.google.com/rss/search?q={query}+{google_search_suffix}&hl=en&gl=US&ceid=US:en"
    ]
    
    # 2. Category-specific subreddits
    subs = category_subreddits.get(category, ["nottheonion" if tone == "funny" else "worldnews"])
    for sub in subs:
        rss_feeds.append(f"https://www.reddit.com/r/{sub}/.rss?limit=30")
    
    # 3. Dedicated niche feeds (Serious only)
    if tone == "serious":
        if category in ("world", "general"):
            rss_feeds.append("https://feeds.bbci.co.uk/news/world/rss.xml")
        elif category == "tech":
            rss_feeds.append("https://feeds.feedburner.com/TechCrunch/")
        elif category == "sports":
            rss_feeds.append("https://www.espn.com/espn/rss/news")
    
    headlines = []
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=48)
    
    for feed_url in rss_feeds:
        try:
            resp = requests.get(feed_url, timeout=10, headers={
                "User-Agent": "ShortsFlow/1.0 (News Aggregator)"
            })
            if resp.status_code != 200:
                continue
            
            root = ET.fromstring(resp.text)
            
            # Handle Atom feeds (Reddit)
            atom_ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", atom_ns):
                title_el = entry.find("atom:title", atom_ns)
                link_el = entry.find("atom:link", atom_ns)
                updated_el = entry.find("atom:updated", atom_ns)
                
                if title_el is not None and title_el.text:
                    # Date check for recency
                    is_fresh = True
                    if updated_el is not None and updated_el.text:
                        try:
                            updated_text = str(updated_el.text).strip()
                            updated_dt = datetime.fromisoformat(updated_text.replace("Z", "+00:00"))
                            if updated_dt < cutoff: is_fresh = False
                        except: pass
                    
                    if is_fresh:
                        link = link_el.get("href", feed_url) if link_el is not None else feed_url
                        headlines.append({
                            "headline": title_el.text.strip(),
                            "source": link,
                            "feed": feed_url
                        })
            
            # Handle RSS 2.0 feeds (BBC, Google News)
            for item in root.findall(".//item"):
                title_el = item.find("title")
                link_el = item.find("link")
                source_el = item.find("source")
                pubDate_el = item.find("pubDate")
                
                if title_el is not None and title_el.text:
                    # Date check for recency
                    is_fresh = True
                    if pubDate_el is not None and pubDate_el.text:
                        try:
                            pub_text = str(pubDate_el.text).strip()
                            pub_dt = email.utils.parsedate_to_datetime(pub_text)
                            if pub_dt < cutoff: is_fresh = False
                        except: pass
                    
                    if is_fresh:
                        source_name = source_el.text if source_el is not None else "News"
                        link = link_el.text if link_el is not None else feed_url
                        headlines.append({
                            "headline": title_el.text.strip(),
                            "source": f"{source_name} ({link})",
                            "feed": feed_url
                        })
                    
        except Exception as e:
            print(f"[Warning] RSS fetch failed for {feed_url}: {e}")
            continue
    
    if not headlines:
        print(f"[Warning] No fresh headlines for {category} ({tone}). Using fallback.")
        headlines = [{
            "headline": f"Breaking development in {category} today" if tone == "serious" else f"Unbelievable {category} story catches everyone off guard",
            "source": "Global News Network",
            "feed": "fallback"
        }]
    
    # Pick a random fresh headline
    chosen = random.choice(headlines)
    real_headline = chosen["headline"]
    real_source = chosen["source"]
    print(f"[Log] NEWS ({tone}): Fresh headline found: \"{real_headline}\" (Source: {real_source})")
    
    # --- STEP 2: Use LLM to rewrite based on tone ---
    url = "https://router.huggingface.co/v1/chat/completions"
    api_headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }
    
    if not HF_API_KEY:
        raise RuntimeError("HF_API_KEY is missing. Cannot rewrite news.")
    
    model = "meta-llama/Llama-3.1-8B-Instruct"
    
    if tone == "funny":
        tone_instruction = """TONE: Sarcastic, funny, disbelief-filled. End with a punchline or "Bro, this actually happened."
HOOK: Rewrite headline as a shocking 6-word hook."""
    else:
        tone_instruction = """TONE: Dramatic, clear, informative. Like a professional anchor delivering breaking news.
HOOK: Rewrite headline as an urgent 6-word hook."""
    
    prompt = f"""Rewrite this REAL news headline as a YouTube Shorts script:

REAL HEADLINE: "{real_headline}"

RULES:
1. DO NOT change the facts. Keep it accurate to the headline.
2. ANCHOR PERSONA: Start with a professional news intro (e.g., "This is your 60-second world report...") and end with a characteristic sign-off.
3. STORY: Retell it in under 45 words. Fast-paced. Use '...' for dramatic pauses in the script.
4. Do NOT add fake details. Only elaborate on what the headline says.
5. NO TECHNICAL NOISE: Do NOT include URLs, version numbers (e.g., v1.0), or "random script things" like JSON keys in the story.
6. DO NOT exaggerate beyond headline facts. No fake details or assumptions.
{tone_instruction}

Format as JSON ONLY:
{{
  "title": "Viral title with emoji",
  "hook": "Short 6-word hook",
  "story": "The retelling of the real news...",
  "search_term": "keyword for background video"
}}
"""

    def llm_call(attempt):
        response_text = get_llm_response(prompt, temperature=0.3 if tone == "funny" else 0.2, max_tokens=400)
        data = robust_json_parse(response_text)
        data["source"] = real_source
        data["original_headline"] = real_headline
        data["tone"] = tone
        return data

    def fallback():
        return {
            "title": f"🚨 {real_headline}",
            "hook": real_headline[:50],
            "story": f"{real_headline}. {'Bro, this actually happened!' if tone == 'funny' else 'More on this developing story.'}",
            "source": real_source,
            "original_headline": real_headline,
            "search_term": "breaking news",
            "tone": tone
        }

    return with_best_of_n(llm_call, validate_news, n=3)

def generate_movie_recap(title):
    """
    Generates a dramatic, high-tension cinematic recap/summary.
    """
    url = "https://router.huggingface.co/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""Generate a high-tension, cinematic STORY RECAP for: "{title}".
    
    STRUCTURE:
    1. THE HOOK: Start with a question or shocking outcome (e.g., "The plan was perfect, until the vault opened...").
    2. THE CLIMAX: Focus on the emotional peak and plot twists.
    3. THE TWIST: Mention a detail that 99% of people missed.
    4. THE LOOP: End with a lead that connects back to the very first word of the hook.

    RULES:
    - Tone: Dramatic, intense, sophisticated.
    - Duration: Target ~300-500 words for long-form.
    - Include specific character names and plot beats.
    - NO spoilers in the hook, but reveal them in the climax.
    
    Format as JSON ONLY:
    {{
      "title": "Recap Title",
      "story": "The full dramatic recap text...",
      "search_term": "Optimized Pexels search query for the movie aesthetic",
      "loop_lead": "Bridge back to hook"
    }}
    """
    
    def llm_call(attempt):
        response_text = get_llm_response(prompt, max_tokens=1500)
        return robust_json_parse(response_text)

    # We reuse validate_story but with higher tolerance for length
    return with_best_of_n(llm_call, lambda d: len(d.get("story", "").split()) > 20, n=3)

def generate_sound_challenge(category="animals"):
    """
    Generates a 'Guess the Sound' challenge script.
    """
    url = "https://router.huggingface.co/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""Generate a 'Guess the Sound' viral challenge for category: {category}.

TASK:
1. Pick a specific object/animal with a distinct sound.
2. Create a 5-word curiosity hook.
3. Provide a 'sound_query' for searching a free sound effect (e.g., 'lion roar', 'old car engine').

RULES:
- Script should be: [HOOK] ... [5 SECONDS SILENCE FOR SOUND] ... [REVEAL]
- Total script under 20 words.
- JSON ONLY.

Format:
{{
  "hook": "Can you guess this sound?",
  "object": "Lion",
  "sound_query": "lion roar",
  "reveal_text": "It was a Lion! Did you get it?"
}}
"""

    def llm_call(attempt):
        response_text = get_llm_response(prompt, temperature=0.7, max_tokens=200)
        return robust_json_parse(response_text)

    return with_best_of_n(llm_call, validate_sound_challenge, n=3)

def generate_trend_script(topic):
    """Generates a viral news script for a specific trending topic."""
    system_prompt = "You are a viral news anchor specializing in high-energy, breaking news reports. ALWAYS respond with RAW JSON."
    prompt = f"""Write a viral 55-second short-form video script about the trending topic: '{topic}'.
    
    STRUCTURE:
    - 0-8s: THE HOOK (Shocking).
    - 8-45s: THE STORY (Drama/Impact).
    - 45-55s: THE LOOP (Seamless connection).
    
    Respond in JSON only:
    {{
      "title": "VIRAL NEWS: {topic}",
      "script": "The full narration text here..."
    }}
    """
    try:
        res = get_llm_response(prompt, system_prompt)
        # Use local function instead of re-importing
        data = robust_json_parse(res)
        if data and isinstance(data, dict) and "script" in data:
            return data
        return None
    except Exception as e:
        print(f"[Error] Failed to generate trend script: {e}")
        return None

def generate_breath_challenge():
    """Generates a script for a viral breathing/hold-your-breath challenge."""
    challenges = [
        {"name": "DEEP SEA DIVE", "dur": 45, "level": "EXTREME"},
        {"name": "MOUNTAIN OXYGEN", "dur": 30, "level": "HARD"},
        {"name": "ZEN MASTER", "dur": 60, "level": "LEGENDARY"}
    ]
    c = random.choice(challenges)
    return {
        "title": f"BREATHING CHALLENGE: {c['name']} 🫁",
        "script": f"Are you ready for the {c['level']} Breathing Challenge? Take a deep breath in 3... 2... 1... HOLD IT! ... ... [Pause for {c['dur']} seconds] ... ... DON'T GIVE UP! You're almost there! ... And... EXHALE! Did you make it? Like and subscribe if you survived!",
        "duration": c['dur']
    }


if __name__ == "__main__":
    res = generate_mixed_facts("science")
    print(f"Hook: {res['hook']}")
    for i, f in enumerate(res["facts"]):
        print(f"{i+1}. {f['fact']} (True: {f['truth']})")
