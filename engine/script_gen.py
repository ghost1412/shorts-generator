import requests
import json
import re
import random
import os
from dotenv import load_dotenv

load_dotenv()

HF_API_KEY = os.getenv("HF_API_KEY")
LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL") # Default Ollama #, "http://localhost:11434/api/chat"
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "qwen3:8b")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def get_llm_response(
    prompt,
    system_prompt="You are a viral YouTube shorts creator. ALWAYS respond with raw JSON only. No conversational text.",
    max_tokens=12000, 
    temperature=0.3,
    model="meta-llama/Llama-3.1-8B-Instruct",
    timeout=300
):
    import requests

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    # 0. Try Gemini API (unless FORCE_OLLAMA is set)
    force_ollama = os.getenv("FORCE_OLLAMA", "").lower() in ["1", "true", "yes"]
    if not force_ollama and GEMINI_API_KEY:
        gemini_models = ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-2.0-flash"]
        for g_model in gemini_models:
            try:
                print(f"[Log] Attempting Gemini API ({g_model})...")
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={GEMINI_API_KEY}"
                headers = {
                    "Content-Type": "application/json"
                }
                payload = {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {"text": f"System instructions:\n{system_prompt}\n\nPrompt:\n{prompt}"}
                            ]
                        }
                    ],
                    "generationConfig": {
                        "temperature": temperature,
                        "maxOutputTokens": max_tokens,
                        "responseMimeType": "application/json"
                    }
                }
                response = requests.post(url, headers=headers, json=payload, timeout=timeout)
                response.raise_for_status()
                res_json = response.json()
                print(f"[DEBUG] Gemini candidates ({g_model}): {json.dumps(res_json.get('candidates', []), indent=2)}")
                content = res_json["candidates"][0]["content"]["parts"][0]["text"]
                print(f"[Log] Gemini API success with {g_model}!")
                return content
            except Exception as e:
                try:
                    if 'response' in locals() and response is not None:
                        print(f"[Warning] Gemini API ({g_model}) failed: {e}. Response: {response.text}")
                    else:
                        print(f"[Warning] Gemini API ({g_model}) failed: {e}")
                except:
                    print(f"[Warning] Gemini API ({g_model}) failed: {e}")
                print("Trying next Gemini model...")

        print("[Warning] All Gemini API models failed. Falling back to other providers...")

    # 1. Try Local LLM (Ollama)
    if LOCAL_LLM_URL:
        try:
            print(f"[Log] Attempting local LLM at {LOCAL_LLM_URL}...")

            payload = {
                "model": LOCAL_LLM_MODEL,  # 🔥 better model
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
                timeout=timeout
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

    hf_timeout = min(timeout, 30)
    response = requests.post(url, headers=headers, json=payload, timeout=hf_timeout)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def with_best_of_n(func, validator, n=3):
    """Retries a generation function up to n times until the validator passes."""
    last_err = None
    for i in range(n):
        try:
            res = func(i)
            if validator(res):
                return res
            print(f"[Log] Validation failed for attempt {i+1}, retrying...")
        except Exception as e:
            print(f"[Log] Attempt {i+1} raised error: {e}")
            last_err = e
    
    if last_err: raise last_err
    raise RuntimeError("Failed to generate valid output after n attempts")

# --- Specific Validators ---

def validate_mixed_facts(data):
    return isinstance(data, dict) and ("hook" in data or "facts" in data)

def validate_story(data):
    if not isinstance(data, dict): return False
    story = data.get("story", "")
    if isinstance(story, list):
        story = " ".join(story)
    elif not isinstance(story, str):
        story = str(story)
    return "title" in data and len(story.split()) > 20

def validate_wyr(data):
    return isinstance(data, dict) and "option_a" in data and "option_b" in data

def validate_reddit(data):
    if not isinstance(data, dict): return False
    story = data.get("story", "")
    if isinstance(story, list):
        story = " ".join(story)
    elif not isinstance(story, str):
        story = str(story)
    return "title" in data and len(story.split()) > 20

def validate_trivia(data):
    return isinstance(data, dict) and "question" in data and "answer" in data

def validate_jwst_script(data):
    return isinstance(data, dict) and "hook" in data and "story" in data

def validate_quote(data):
    return isinstance(data, dict) and "quote" in data and len(data.get("quote", "").split()) >= 5

def validate_news(data):
    return isinstance(data, dict) and "story" in data and len(data.get("story", "").split()) > 10

def validate_sound_challenge(data):
    return isinstance(data, dict) and "hook" in data and "sound_query" in data

def validate_odd_one_out(data):
    return isinstance(data, dict) and "hook" in data and "theme" in data

def validate_riddle(data):
    return isinstance(data, dict) and "question" in data and "answer" in data and "search_term" in data

def validate_manim(data):
    if not isinstance(data, dict):
        return False
    if "code" not in data or "title" not in data or "voiceover_text" not in data:
        return False
    
    code = data.get("code", "")
    voiceover = data.get("voiceover_text", "")
    
    if not isinstance(code, str) or not isinstance(voiceover, str):
        return False
        
    cleaned_voiceover = voiceover.strip()
    if len(cleaned_voiceover) < 15 or not (cleaned_voiceover.endswith('.') or cleaned_voiceover.endswith('!') or cleaned_voiceover.endswith('?')):
        print("[Log] Validation failed: voiceover_text is incomplete or missing sentence-ending punctuation.")
        return False

    if "Tex(" in code or "MathTex(" in code:
        print("[Log] Validation failed: code contains Tex or MathTex (LaTeX not supported).")
        return False

    if "ExplainerScene" not in code:
        print("[Log] Validation failed: code missing ExplainerScene class.")
        return False

    import ast
    try:
        ast.parse(code)
    except SyntaxError as e:
        print(f"[Log] Validation failed: Python SyntaxError in code ({e}).")
        return False

    return True

# --- Generation Functions ---

def generate_manim_script(topic, extract_mode="shorts"):
    """
    Generates a Manim CE Python script for an educational explainer.
    Supports extract_mode='shorts' (vertical 9:16 format) or 'long' (horizontal 16:9 format).
    Returns: {"title": str, "code": str, "voiceover_text": str}
    """
    is_shorts = (extract_mode == "shorts")
    layout_instructions = """11. VERTICAL SHORTS LAYOUT (9:16 ASPECT RATIO):
    - This video is formatted for YouTube Shorts / Reels / TikTok (9:16 vertical screen).
    - Visible screen coordinate bounds: x is narrow [-3.8, 3.8], y is tall [-6.5, 6.5].
    - Stack all titles, diagrams, text, and labels VERTICALLY from top to bottom (e.g. `VGroup(...).arrange(DOWN, buff=0.4)` or `.next_to(..., DOWN)`).
    - Keep text lines short and font sizes modest (e.g., font_size=24-32 for descriptions, font_size=34-40 for main titles) so nothing gets clipped on mobile screens on the left or right edges.""" if is_shorts else """11. HORIZONTAL WIDESCREEN LAYOUT (16:9 ASPECT RATIO):
    - This video is formatted for traditional 16:9 widescreen display.
    - Screen bounds: x [-6.5, 6.5], y [-3.8, 3.8]. Utilize horizontal space cleanly."""

    prompt = f"""Generate a Manim Community Edition (manim) Python script explaining {topic}.
REQUIREMENTS:
1. The script MUST contain a single class inheriting from Scene named ExplainerScene (e.g. `class ExplainerScene(Scene):`).
2. Use Manim CE syntax (e.g., `self.play(Create(...))`, `self.play(Write(...))`, `self.play(Transform(...))`).
3. CRITICAL: DO NOT use `Tex()` or `MathTex()`. The system does NOT have LaTeX installed. You MUST use `Text("your text")` or `MarkupText("your text")` for all text, numbers, and equations (e.g., `Text("a² + b² = c²")`).
4. Keep the animation clean, professional, and visually engaging (20-30 seconds). Focus on clear geometric figures and labels.
5. GEOMETRIC ACCURACY FOR TOPICS:
   - If the topic is 'Pythagorean Theorem' or related to right triangles:
     * You MUST draw a clear right-angled triangle first using `Polygon` (e.g. `Polygon([-2, -1, 0], [1, -1, 0], [1, 1.25, 0], color=BLUE)` where the legs meet at a 90-degree right angle).
     * DO NOT draw just a square or rectangle as the primary subject. The right-angled triangle with legs 'a', 'b' and hypotenuse 'c' MUST be the central visual element.
     * Optionally add squares attached to the sides a, b, and c to visually illustrate a² + b² = c², or highlight the sides and show the formula `Text("a² + b² = c²")`.
   - For all geometry topics, ensure the shapes accurately represent the math principles being taught.
6. Include a complete, clear, multi-sentence voiceover script ("voiceover_text") that thoroughly explains the topic from start to finish. The script MUST end with proper punctuation (period, exclamation mark).
7. Do NOT include markdown blocks in the "code" field. The "code" field MUST be valid raw Python code starting with `from manim import *`.
8. CRITICAL SYNTAX: When creating polygons or lines, use 3D coordinates as lists. Correct: `Polygon([-3, 0, 0], [0, 0, 0], [0, 4, 0])`. Incorrect: `Polygon([(-3, 0), (0, 0)])`.
9. CRITICAL SPACING: DO NOT let text or shapes overlap! Use `.next_to()`, `.shift()`, or `VGroup(...).arrange(...)` to spread items out cleanly across the screen.
10. MANIM COLORS: Use standard Manim color constants like `BLUE`, `TEAL`, `GREEN`, `YELLOW`, `RED`, `PURPLE`, `ORANGE`, `GOLD`, `WHITE`, `GRAY`, `PINK`, or hex strings (e.g. `"#00FFFF"`).
{layout_instructions}

Format as JSON ONLY:
{{
  "title": "Title of the explainer",
  "code": "from manim import *\\n\\nclass ExplainerScene(Scene):\\n    def construct(self):\\n        ...",
  "voiceover_text": "The complete voiceover script to be spoken during this animation."
}}
"""
    def llm_call(attempt):
        response_text = get_llm_response(prompt, temperature=0.3, max_tokens=8192)
        return robust_json_parse(response_text)
    
    return with_best_of_n(llm_call, validate_manim, n=3)

def generate_mixed_facts(category="science"):
    """
    Generates a curiosity-driven 'True or False' fact list.
    Returns: {"hook": str, "facts": [{"fact": str, "truth": bool}]}
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
    selected_sub = get_sub_topic(category)
    print(f"[Log] FACTS: Selected sub-topic: {selected_sub}")
    
    prompt = f"""Generate EXACTLY 3 SHOCKING and BIZARRE facts about {selected_sub}.
    One of them MUST be a plausible-sounding LIE (False), the others must be TRUE.
    
    RULES:
    1. Focus on OBSCURE, weird, or mind-blowing topics.
    2. The LIE must be hard to distinguish from the truth (don't make it obvious like 'cats are aliens').
    3. NO TECHNICAL NOISE: Do NOT include URLs, version numbers (e.g., v1.0), or "random script things" like JSON keys.
    4. Format as JSON ONLY:
    
    {{
      "hook": "99% of people fail this... Can you spot the lie about {selected_sub}?",
      "facts": [
        {{"fact": "shocking fact text", "truth": true}},
        {{"fact": "another shocking fact", "truth": true}},
        {{"fact": "plausible lie text", "truth": false}}
      ],
      "loop_lead": "Wait, did you catch the first one?"
    }}
    """

    def llm_call(attempt):
        response_text = get_llm_response(prompt, temperature=0.8, max_tokens=512)
        return robust_json_parse(response_text)

    return with_best_of_n(llm_call, validate_mixed_facts, n=3)

def generate_story(category="general", hero=None, hero_name=None, companion=None, quest=None, setting=None):
    """
    Generates a dramatic or emotional viral story.
    Supports interactive/kids mode story customization.
    Returns: {"title": str, "story": str}
    """
    if hero:
        prompt = f"Write a charming, magical, and educational children's bedtime story about a hero named {hero_name or 'Buddy'} who is a {hero}. The hero's companion is a {companion or 'friend'}. Their adventure is to {quest or 'explore'} in the setting of {setting or 'a magical land'}. Focus on a fun, gentle, and heartwarming adventure with a positive moral. Keep it simple, sweet, and under 100 words. Respond in JSON ONLY: {{'title': '...', 'story': '...', 'loop_lead': 'And that is why...'}}"
    else:
        known_cats = ["science", "space", "animals", "history", "anime_lore", "intimacy_facts", "facts", "wyr", "trivia", "quotes", "sound_challenge", "kids", "children", "bedtime"]
        selected_sub = category if (len(category.split()) > 1 or category.lower() not in known_cats) else get_sub_topic(category)
        print(f"[Log] STORY: Selected sub-topic/prompt: {selected_sub}")
        
        is_kids = category.lower() in ["kids", "children", "bedtime", "children_story"]
        if is_kids:
            prompt = f"Write a charming, magical, and educational children's bedtime story about {selected_sub}. Focus on a fun, gentle, and heartwarming adventure with a positive moral. Keep it simple, sweet, and under 100 words. Respond in JSON ONLY: {{'title': '...', 'story': '...', 'loop_lead': 'And that is why...'}}"
        else:
            prompt = f"Write a SHOCKING, high-drama 1st-person story about {selected_sub}. Focus on a bizarre personal experience. Keep it under 100 words. Respond in JSON ONLY: {{'title': '...', 'story': '...', 'loop_lead': 'And that is why...'}}"
    
    def llm_call(attempt):
        response_text = get_llm_response(prompt, temperature=0.7, max_tokens=600)
        return robust_json_parse(response_text)
    
    return with_best_of_n(llm_call, validate_story, n=3)

def _clean_json_string(s):
    """Internal helper to clean comments, control chars, and trailing commas."""
    import re
    # 1. Remove control characters
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', s)
    # 2. Fix unescaped newlines/tabs inside strings (heuristic)
    def fix_whitespace(m):
        return m.group(0).replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    s = re.sub(r'"[^"]*?"', fix_whitespace, s, flags=re.DOTALL)
    # 3. Strip comments
    s = re.sub(r'//.*?\n', '', s)
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.DOTALL)
    # 4. Fix trailing commas (e.g. [1, 2, ])
    s = re.sub(r',\s*([\]\}])', r'\1', s)
    return s.strip()

def robust_json_parse(output):
    """Extreme multi-strategy JSON extraction for unreliable LLM outputs."""
    import re, json
    if not output: return None
    
    def get_balanced(text):
        start_idx = -1
        for i, char in enumerate(text):
            if char in ('{', '['):
                start_idx = i
                break
        if start_idx == -1: return None
        
        stack = []
        in_string = False
        escaped = False
        for i in range(start_idx, len(text)):
            char = text[i]
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
                        if not stack: return text[start_idx:i+1]
        
        # 🟢 TRUNCATION RECOVERY: If we reach end of text but stack is not empty, append missing closers
        if stack:
            recovered = text[start_idx:]
            # Close any open string
            if in_string: recovered += '"'
            # Close all balanced objects/arrays
            recovered += "".join(reversed(stack))
            return recovered
        return None

    # strategy 1: Direct Balanced Clean & Parse
    json_candidate = get_balanced(output)
    if json_candidate:
        try:
            return json.loads(_clean_json_string(json_candidate))
        except:
            pass
            
    # strategy 2: Greedy Recovery (for Fragmented or Large Lists)
    collected_objects = []
    # Find every starting '{' and try to extract a balanced object
    for i in range(len(output)):
        if output[i] == '{':
            candidate = get_balanced(output[i:])
            if candidate:
                try:
                    obj = json.loads(_clean_json_string(candidate))
                    if obj not in collected_objects:
                        collected_objects.append(obj)
                except:
                    continue
    
    if collected_objects:
        print(f"[Log] Recovered {len(collected_objects)} valid objects via greedy extraction.")
        return collected_objects

    # strategy 3: Regex Timestamp/Segment Recovery (Last Resort)
    print("[Log] JSON parsing failed all strategies, attempting Regex segment recovery...")
    patterns = [
        r"(\d+\.?\d*)\s*s?\s*[\-\–\—to,:]+\s*(\d+\.?\d*)\s*s?", # 10.5s - 20.1s
        r"(\d{1,2}:\d{2}:?\d{0,2})\s*[\-\–\—to,]+\s*(\d{1,2}:\d{2}:?\d{0,2})", # 01:23 - 01:45
        r'''\"?start\"?[\"':\s]+[\"']?(\d+\.?\d*m?s?)[\"']?[\s,]*\"?end\"?[\"':\s]+[\"']?(\d+\.?\d*m?s?)[\"']?''', # Quote-resilient
    ]
    
    def time_to_sec(ts):
        ts = str(ts).lower().replace("s", "").replace("m", "").strip()
        if ":" not in ts: return float(ts)
        parts = ts.split(":")
        if len(parts) == 3: return int(parts[0])*3600 + int(parts[1])*60 + float(parts[2])
        return int(parts[0])*60 + float(parts[1])

    segments = []
    for p in patterns:
        matches = re.findall(p, output, re.IGNORECASE)
        for m in matches:
            try:
                s_str = m[0] if isinstance(m, tuple) else m
                e_str = m[1] if isinstance(m, tuple) else ""
                if not e_str: continue 
                s_val = time_to_sec(s_str)
                e_val = time_to_sec(e_str)
                if e_val > s_val:
                    if not any(s['start'] == s_val and s['end'] == e_val for s in segments):
                        segments.append({"start": s_val, "end": e_val, "viral_score": 75, "reason": "High-Impact Sequence"})
            except: continue
    
    if segments: 
        return {"highlights": segments, "segments": segments}
    
    # strategy 4: Emergency Plaintext Fallback
    clean_output = output.strip()
    if len(clean_output) > 20 and "error" not in clean_output.lower():
        print("[Log] JSON/Regex failed. Returning raw text as emergency fallback.")
        return {
            "script": clean_output, 
            "story": clean_output, 
            "highlights": [{"start": 30.0, "end": 60.0, "reason": "Viral Highlight"}],
            "segments": [{"start": 30.0, "end": 60.0, "reason": "Viral Highlight"}],
            "facts": [{"fact": clean_output, "truth": True}], 
            "hook": "Did you know?", 
            "title": "Viral Update"
        }

    return None

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
        "facts": ["the ocean floor", "human brain glitches", "unexpected history", "science of sleep", "unsolved mysteries", "nature's survivalists"],
        "wyr": ["awkward social dilemmas", "impossible survival choices", "weird superpower trade-offs", "historical alternate realities", "bizarre sensory swaps"],
        "trivia": ["unbelievable geography", "forgotten inventions", "extreme nature", "pop culture butterfly effects", "obscure mythology"],
        "quotes": ["stoic wisdom for chaos", "cinematic metaphors", "minimalist life philosophy", "forgotten ancient scrolls", "poetic nihilism"],
        "sound_challenge": ["rare animals", "vintage machinery", "unknown instruments", "nature's whispers", "mechanical failures"],
        "kids": ["a magical forest adventure", "a friendly dragon who lost his fire", "the puppy who learned to share", "a curious squirrel and the magical acorn", "the sleepy teddy bear's adventure", "the star that forgot how to shine", "the little boat that crossed the pond", "a baby elephant learning to swim"],
        "children": ["a magical forest adventure", "a friendly dragon who lost his fire", "the puppy who learned to share", "a curious squirrel and the magical acorn", "the sleepy teddy bear's adventure", "the star that forgot how to shine", "the little boat that crossed the pond", "a baby elephant learning to swim"],
        "bedtime": ["a magical forest adventure", "a friendly dragon who lost his fire", "the puppy who learned to share", "a curious squirrel and the magical acorn", "the sleepy teddy bear's adventure", "the star that forgot how to shine", "the little boat that crossed the pond", "a baby elephant learning to swim"]
    }
    
    # Try direct mapping first
    if category.lower() in sub_topics:
        return random.choice(sub_topics[category.lower()])
    
    # Fallback to random if not found
    all_subs = [item for sublist in sub_topics.values() for item in sublist]
    return random.choice(all_subs)

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
        if vyr.get("percent_a", 0) + wyr.get("percent_b", 0) != 100:
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
  "story": "The full story text...",
  "loop_lead": "But wait, it gets crazier..."
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
  "answer": "Correct Option Text",
  "loop_lead": "Could you do better next time?"
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
  "author": "Author Name",
  "loop_lead": "Think about it..."
}}
"""

    def llm_call(attempt):
        response_text = get_llm_response(prompt, temperature=0.2, max_tokens=400)
        return robust_json_parse(response_text)

    return with_best_of_n(llm_call, validate_quote, n=3)

def generate_funny_news(category="general", tone="funny", persona=None):
    """
    Fetches REAL news from RSS feeds, then uses LLM to rewrite in the chosen tone or persona.
    tone: "funny" = bizarre/sarcastic, "serious" = dramatic/informative
    persona: "rabbit", "robot", "squirrel", "superhero" etc.
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
    google_search_suffix = "weird bizarre funny" if tone == "funny" or persona else "latest breaking"
    rss_feeds = [
        f"https://news.google.com/rss/search?q={query}+{google_search_suffix}&hl=en&gl=US&ceid=US:en"
    ]
    
    # 2. Category-specific subreddits
    subs = category_subreddits.get(category, ["nottheonion" if tone == "funny" or persona else "worldnews"])
    for sub in subs:
        rss_feeds.append(f"https://www.reddit.com/r/{sub}/.rss?limit=30")
    
    # 3. Dedicated niche feeds (Serious only)
    if tone == "serious" and not persona:
        if category in ("world", "general"):
            rss_feeds.append("https://feeds.bbci.co.uk/news/world/rss.xml")
        elif category == "tech":
            rss_feeds.append("https://feeds.feedburner.com/TechCrunch/")
        elif category == "sports":
            rss_feeds.append("https://www.espn.com/espn/rss/news")
    
    # 🟢 UPGRADE: Persona-Driven Funny News
    persona_prompt = ""
    if persona:
        p = persona.lower()
        if p == "rabbit":
            persona_prompt = "ACT AS A HYPERACTIVE RABBIT: Use words like 'Boing!', 'Crunchy!', 'Hop to it!', and be EXTREMELY energetic and fast-paced."
        elif p == "robot":
            persona_prompt = "ACT AS A SARCASTIC ROBOT: Use technical jargon, beep-boop sounds, and be cold, calculated, and slightly condescending."
        elif p == "squirrel":
            persona_prompt = "ACT AS A PANICKED SQUIRREL: Mention nuts, be very distracted, use short sentences, and act like everything is a crisis."
        elif p == "superhero":
            persona_prompt = "ACT AS A BOOMING SUPERHERO: Be heroic, mention justice, use epic metaphors, and act like you're saving the world with this news."
        elif p == "old_man":
            persona_prompt = "ACT AS A GRUMPY OLD MAN: Complain about 'kids these days', mention 'the good old days', and be skeptical of everything."
        elif p == "mafia_cat":
            persona_prompt = "ACT AS A MAFIA CAT BOSS: Speak with a raspy voice, use 'family' metaphors, mention 'making an offer', and be cool, intimidating, and mysterious."
        else:
            persona_prompt = f"ACT AS A {persona.upper()}: Use appropriate slang, interjections, and personality traits."
    
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
        print(f"[Warning] No fresh headlines for {category}. Using fallback.")
        headlines = [{
            "headline": f"Breaking development in {category} today" if tone == "serious" else f"Unbelievable {category} story catches everyone off guard",
            "source": "Global News Network",
            "feed": "fallback"
        }]
    
    # Pick a random fresh headline
    chosen = random.choice(headlines)
    real_headline = chosen["headline"]
    real_source = chosen["source"]
    print(f"[Log] NEWS ({persona or tone}): Fresh headline found: \"{real_headline}\" (Source: {real_source})")
    
    # --- STEP 2: Use LLM to rewrite based on tone/persona ---
    url = "https://router.huggingface.co/v1/chat/completions"
    api_headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }
    
    if not HF_API_KEY:
        raise RuntimeError("HF_API_KEY is missing. Cannot rewrite news.")
    
    model = "meta-llama/Llama-3.1-8B-Instruct"
    
    if persona:
        tone_instruction = f"""PERSONA: You are a {persona}. 
        Use characteristic slang, sounds, and interjections (e.g., if Rabbit, use "Boing! What's up docs?"; if Robot, use "Beep Boop - Processing...").
        Be EXTREMELY expressive and funny."""
    elif tone == "funny":
        tone_instruction = """TONE: Sarcastic, funny, disbelief-filled. End with a punchline or "Bro, this actually happened." 
        HOOK: Rewrite headline as a shocking 6-word hook."""
    else:
        tone_instruction = """TONE: Dramatic, clear, informative. Like a professional anchor delivering breaking news.
        HOOK: Rewrite headline as an urgent 6-word hook."""
    
    prompt = f"""Rewrite this REAL news headline as a YouTube Shorts script:
    
REAL HEADLINE: "{real_headline}"

RULES:
1. DO NOT change the facts. Keep it accurate to the headline.
2. ANCHOR PERSONA: Start with a professional news intro AND your character intro if applicable. 
3. STORY: Retell it in under 45 words. Fast-paced. Use '...' for dramatic pauses.
4. If persona is set, integrate it into EVERY line. 
5. NO TECHNICAL NOISE: Do NOT include URLs or version numbers in the story.
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

    try:
        return with_best_of_n(llm_call, validate_news, n=3)
    except Exception as e:
        print(f"[Warning] News LLM failed ({e}). Using emergency fallback.")
        return fallback()

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

def generate_odd_one_out_script(category="general"):
    """
    Generates a funny and engaging script for 'Odd One Out' mode.
    """
    selected_sub = get_sub_topic(category)
    prompt = f"""Generate a funny, high-energy YouTube Shorts hook and theme for an 'Odd One Out' game about {selected_sub}.
RULES:
1. Make the hook extremely engaging (e.g., "99% of people fail this...").
2. Focus on OBSCURE or BIZARRE themes.
3. The 'theme' should be a short description of what person/thing is 'different' (e.g., "One of these Doge emojis is actually a cat").
4. Respond in JSON ONLY.

Format:
{{
  "hook": "Only GIGACHADS can find this! 🗿",
  "theme": "One of these is NOT a {selected_sub}...",
  "hint": "Look closely at the rotations!"
}}
"""
    def llm_call(attempt):
        response_text = get_llm_response(prompt, temperature=0.8, max_tokens=256)
        return robust_json_parse(response_text)

    return with_best_of_n(llm_call, validate_odd_one_out, n=3)

def generate_riddle(category="general"):
    """
    Generates a SHORT lateral-thinking riddle ('What am I?').
    """
    selected_sub = get_sub_topic(category)
    prompt = f"""Generate a classic 'What am I?' lateral-thinking riddle about {selected_sub}.
RULES:
1. Avoid trivia, history facts, or GK. (e.g., "Who was Einstein?" is BAD).
2. Use wordplay or metaphorical descriptions. (e.g., "I have a face but no eyes..." is GOOD).
3. The riddle should be SHORT (max 15 words) and EASY for viral engagement.
4. Provide a 'hint' and the 'answer'.
5. Provide a 'search_term' for a visual clue (e.g., 'river' or 'clock').
6. Respond in JSON ONLY.

Format:
{{
  "question": "The lateral thinking riddle here...",
  "hint": "One word clue...",
  "answer": "The answer",
  "hook": "GENIUS TEST! 🧠",
  "search_term": "visual clue keyword"
}}
"""
    def llm_call(attempt):
        response_text = get_llm_response(prompt, temperature=0.7, max_tokens=256)
        return robust_json_parse(response_text)

    return with_best_of_n(llm_call, validate_riddle, n=3)

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

def generate_jwst_script():
    """
    Generates a viral script for James Webb Space Telescope images.
    """
    prompt = """Generate a mind-blowing script for a YouTube Short featuring new images from the James Webb Space Telescope (JWST).
    
    STRUCTURE:
    1. THE HOOK: A 6-word shocking opener about space or the telescope's power.
    2. THE STORY: A short, fast-paced narration (under 50 words) that expresses wonder at the "newest images" and mentions things like "deepest view of the universe" or "nebula details".
    3. THE LOOP: A lead that connects back to the start.

    RULES:
    - Tone: Epic, mysterious, awe-inspiring.
    - NO TECHNICAL NOISE.
    - Format as JSON ONLY.

    {{
      "title": "JWST: New Galaxy Found! 🌌",
      "hook": "NASA just released these new images...",
      "story": "The James Webb Telescope just peered deeper into the void than ever before. These new images reveal galaxies from the dawn of time, looking back 13 billion years. It's not just space... it's a time machine.",
      "loop_lead": "Wait until you see the first one..."
    }}
    """
    
    def llm_call(attempt):
        response_text = get_llm_response(prompt, temperature=0.7, max_tokens=400)
        return robust_json_parse(response_text)

    return with_best_of_n(llm_call, validate_jwst_script, n=3)


def generate_trailer_missed_script(title):
    """
    Generates a viral script about hidden details/easter eggs missed in a trailer.
    """
    prompt = f"""Write a viral, high-energy YouTube Shorts script about 3 hidden details, secrets, or easter eggs people missed in the trailer for "{title}".
    
    STRUCTURE:
    1. THE HOOK: A shocking opening statement (e.g., "GTA 6 just changed everything, and you missed this massive detail...").
    2. THE DETAILS: Mention 2-3 specific, mind-blowing easter eggs or hidden frames.
    3. THE LOOP: A seamless transition loop back to the first word of the hook.
    
    RULES:
    - Tone: Enthusiastic, shocking, fast-paced.
    - Word count: Under 90 words.
    - Format as JSON ONLY:
    
    {{
      "title": "Secrets in the {title} Trailer",
      "story": "The full voiceover script text here...",
      "search_term": "action cinematic",
      "loop_lead": "Go back and check for yourself..."
    }}
    """
    def llm_call(attempt):
        response_text = get_llm_response(prompt, max_tokens=600)
        data = robust_json_parse(response_text)
        if isinstance(data, dict) and "story" in data:
            story = data["story"]
            if isinstance(story, list):
                data["story"] = " ".join(story)
            elif not isinstance(story, str):
                data["story"] = str(story)
        return data

    return with_best_of_n(llm_call, validate_story, n=3)





if __name__ == "__main__":
    res = generate_mixed_facts("science")
    print(f"Hook: {res['hook']}")
    for i, f in enumerate(res["facts"]):
        print(f"{i+1}. {f['fact']} (True: {f['truth']})")
