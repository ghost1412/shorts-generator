import requests
import json
import re
import random
import os
import time
from dotenv import load_dotenv

load_dotenv()

HF_API_KEY = os.getenv("HF_API_KEY")
LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:11434/api/chat")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "qwen3:8b")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
LLM_PROVIDER_ENV = os.getenv("LLM_PROVIDER", "auto").lower()
LLM_MODEL_ENV = os.getenv("LLM_MODEL")
LLM_BASE_URL_ENV = os.getenv("LLM_BASE_URL")

def auto_detect_video_filter(user_context=None, style_context=None, category=None, prompt=None):
    """Analyzes context text and determines the optimal visual color grade filter preset."""
    text_corpus = f"{user_context or ''} {style_context or ''} {category or ''} {prompt or ''}".lower()
    
    # 1. Fast Keyword Heuristics (Generic Visual & Genre Terms)
    if any(k in text_corpus for k in ["samurai", "katana", "kurosawa", "bushido", "feudal", "black and white", "monochrome", "sword duel"]):
        return "kurosawa"
    if any(k in text_corpus for k in ["cyberpunk", "neon", "synthwave", "night race", "high speed drift", "futuristic", "sci-fi"]):
        return "cyberpunk"
    if any(k in text_corpus for k in ["action", "pursuit", "crash", "combat", "emp", "explosion", "strike", "rally", "fast cuts", "chase"]):
        return "vibrant_action"
    if any(k in text_corpus for k in ["scenery", "landscape", "vista", "golden hour", "sunset", "nature", "peaceful", "serene", "scenic"]):
        return "cinematic_warm"
    if any(k in text_corpus for k in ["vhs", "retro", "90s", "80s", "analog", "nostalgic", "camcorder", "scanlines"]):
        return "vintage_vhs"
    if any(k in text_corpus for k in ["horror", "spooky", "scary", "dark fantasy", "shadow", "thriller", "creepy"]):
        return "moody_dark"
    if any(k in text_corpus for k in ["movie recap", "cinematic film", "blockbuster", "trailer", "dramatic story"]):
        return "teal_orange"

    # 2. LLM Fallback Classifier
    try:
        llm_prompt = f"""
Given the following video description:
"{text_corpus}"

Choose the SINGLE BEST visual color grade filter from this list:
- kurosawa (High-contrast B&W samurai style)
- teal_orange (Blockbuster cinematic movie style)
- cyberpunk (Neon boosted contrast for night/sci-fi/racing)
- cinematic_warm (Golden hour warmth for scenery and story)
- vibrant_action (Sharp high-contrast for combat and sports)
- vintage_vhs (Analog retro tape aesthetic)
- moody_dark (Low-key contrast for dark/horror)

Respond with raw JSON: {{"filter": "<preset_name>"}}
"""
        response = get_llm_response(llm_prompt, system_prompt="You are a color grading expert. Return raw JSON only.")
    except Exception as e:
        print(f"[Warning] AI Auto Filter fallback: {e}")
        
    return "none"

def generate_clip_commentary_hook(transcript_text, category="general"):
    """Generates a dynamic 8-15 word contextual AI commentary reaction for video clips."""
    raw_text = str(transcript_text or "").strip()
    if not raw_text or raw_text.lower() in ["viral moment", "none", "clip"]:
        raw_text = f"{category} video moment"

    prompt = f"""You are an elite viral YouTube Shorts commentator and reaction host.
Analyze the clip content below:
"{raw_text[:600]}"

Category: {category}

Write a 1-sentence viral commentary intro (8 to 15 words) that specifically reacts to what is being said or happening in this clip.

RULES:
- NEVER say generic fluff like "This viral moment will blow your mind" or "Wait till the end!" or "You won't believe this!".
- Comment specifically on the topic, situation, statement, or funny conflict in the clip snippet.
- Sound like a sharp, witty, or amazed real commentator introducing a wild moment.

Return raw JSON only: {{"hook": "<your specific 8-15 word commentary reaction>"}}
"""
    try:
        response = get_llm_response(prompt, system_prompt="You are a viral shorts commentator. Respond with valid JSON only.")
        data = robust_json_parse(response)
        if isinstance(data, dict) and data.get("hook"):
            hook = data["hook"].strip()
            if not any(bad in hook.lower() for bad in ["blow your mind", "viral moment", "wait till the end"]):
                return hook
    except Exception as e:
        print(f"[Warning] Failed to generate commentary hook via LLM: {e}")
    
    fallbacks = [
        "Listen closely to how this conversation completely flipped.",
        "He really thought he could pull this off without anyone noticing.",
        "Watch how fast the energy changes in this exact moment.",
        "Nobody was expecting this answer to come out of nowhere."
    ]
    return random.choice(fallbacks)

def generate_dynamic_filter_timeline(total_duration, user_context=None, transcript_data=None, scene_description=None):

    """Generates clip-specific timestamped filter cuts based on LLM transcript & scene analysis."""
    if total_duration <= 0:
        return []

    # 1. Try Gemini LLM for clip-specific dynamic scene grading
    try:
        context_text = f"User Context: {user_context or 'General'}\nScene Description: {scene_description or 'Video clip'}"
        if transcript_data and isinstance(transcript_data, dict):
            segs = transcript_data.get('segments', [])
            words_preview = " ".join([s.get('text', '') for s in segs if isinstance(s, dict) and s.get('text')])
            if words_preview:
                context_text += f"\nClip Transcript: {words_preview[:300]}"

        prompt = f"""You are an expert film colorist. Analyze this specific video clip (Duration: {total_duration:.1f}s):
{context_text}

Choose visual color grade filters for this clip from these available presets:
Available Presets: ["none", "kurosawa", "teal_orange", "cyberpunk", "cinematic_warm", "vibrant_action", "vintage_vhs", "moody_dark", "anime_vivid", "matrix_green", "sepia_western", "cold_thriller", "hdr_pop"]

CREATIVE DIRECTIVE & FREEDOM:
1. UNIFORM MOOD / SINGLE GRADE: If the clip maintains a single consistent mood, aesthetic, or visual style throughout, assign 1 SINGLE filter across the ENTIRE duration (from 0.0 to {total_duration:.1f}s).
2. DYNAMIC TRANSITIONS: If the clip undergoes clear narrative shifts, action escalations, or dramatic mood transitions, divide it into 2 to 3 timestamp ranges with appropriate filter presets.
3. Use "none" for natural lighting or scenes that do not require heavy grading.

Respond strictly with raw JSON:
[
  {{"start": 0.0, "end": {total_duration:.1f}, "filter": "preset_name"}}
]
or for dynamic shifts:
[
  {{"start": 0.0, "end": 12.5, "filter": "preset1"}},
  {{"start": 12.5, "end": {total_duration:.1f}, "filter": "preset2"}}
]
"""
        response = get_llm_response(prompt, system_prompt="You are a video colorist. Output raw JSON array only.")
        parsed = json.loads(response)
        if isinstance(parsed, list) and len(parsed) > 0:
            valid_cuts = []
            for item in parsed:
                f_name = str(item.get("filter", "none")).lower().strip()
                st = float(item.get("start", 0.0))
                et = float(item.get("end", total_duration))
                if et > st:
                    valid_cuts.append({"start": st, "end": et, "filter": f_name})
            if valid_cuts:
                print(f"[Log] 🧠 Gemini AI Dynamic Timeline generated ({len(valid_cuts)} cuts): {valid_cuts}")
                return valid_cuts
    except Exception as e:
        print(f"[Warning] LLM Dynamic filter call failed: {e}. Falling back to context heuristic.")

    # 2. Dynamic Fallback: Clip-specific heuristic variations using hashing for uniqueness
    text_corpus = f"{user_context or ''} {scene_description or ''}".lower()
    
    is_samurai = any(k in text_corpus for k in ["samurai", "katana", "kurosawa", "bushido", "feudal", "duel", "tsushima"])
    is_cyber = any(k in text_corpus for k in ["cyberpunk", "neon", "synthwave", "night race", "drift", "sci-fi"])
    is_horror = any(k in text_corpus for k in ["horror", "spooky", "scary", "dark", "shadow", "thriller"])
    is_action = any(k in text_corpus for k in ["action", "pursuit", "crash", "combat", "explosion", "chase", "standoff", "fight"])
    
    # Generate unique seed per clip based on text hash & duration
    import hashlib
    hash_val = int(hashlib.md5(f"{text_corpus}_{total_duration}".encode('utf-8')).hexdigest(), 16)
    
    # Decide whether this clip is best served by 1 consistent filter or multi-phase transitions
    prefer_single_filter = (hash_val % 2 == 0) or total_duration <= 12.0

    presets_pool = ["kurosawa", "vibrant_action", "cinematic_warm", "teal_orange", "hdr_pop", "moody_dark", "sepia_western"]
    f1 = presets_pool[hash_val % len(presets_pool)]
    f2 = presets_pool[(hash_val + 2) % len(presets_pool)]

    cuts = []
    if prefer_single_filter:
        target_f = "kurosawa" if is_samurai else ("cyberpunk" if is_cyber else ("moody_dark" if is_horror else ("vibrant_action" if is_action else f1)))
        cuts = [{"start": 0.0, "end": round(total_duration, 2), "filter": target_f}]
    else:
        offset1 = 0.25 + (hash_val % 15) * 0.01
        p1 = round(total_duration * offset1, 2)
        if is_samurai:
            cuts = [{"start": 0.0, "end": p1, "filter": "kurosawa"}, {"start": p1, "end": round(total_duration, 2), "filter": "cinematic_warm"}]
        elif is_cyber:
            cuts = [{"start": 0.0, "end": p1, "filter": "cyberpunk"}, {"start": p1, "end": round(total_duration, 2), "filter": "hdr_pop"}]
        elif is_horror:
            cuts = [{"start": 0.0, "end": p1, "filter": "moody_dark"}, {"start": p1, "end": round(total_duration, 2), "filter": "cold_thriller"}]
        elif is_action:
            cuts = [{"start": 0.0, "end": p1, "filter": "vibrant_action"}, {"start": p1, "end": round(total_duration, 2), "filter": "teal_orange"}]
        else:
            cuts = [{"start": 0.0, "end": p1, "filter": f1}, {"start": p1, "end": round(total_duration, 2), "filter": f2}]
            
    print(f"[Log] 🧠 Dynamic Timeline generated ({len(cuts)} phases over {total_duration:.1f}s): {cuts}")
    return cuts

def _call_openai_compatible(api_key, base_url, model, prompt, system_prompt, max_tokens=4096, temperature=0.3, timeout=120, extra_headers=None):
    import requests
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    if extra_headers:
        headers.update(extra_headers)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    resp = requests.post(base_url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]

def _call_anthropic(api_key, model, prompt, system_prompt, max_tokens=4096, temperature=0.3, timeout=120):
    import requests
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01"
    }
    payload = {
        "model": model or "claude-3-5-haiku-20241022",
        "max_tokens": max_tokens,
        "system": system_prompt or "",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data["content"][0]["text"]

def get_llm_response(
    prompt,
    system_prompt="You are a viral YouTube shorts creator. ALWAYS respond with raw JSON only. No conversational text.",
    max_tokens=12000, 
    temperature=0.3,
    model=None,
    provider=None,
    base_url=None,
    timeout=300
):
    import requests
    import time


    target_provider = (provider or os.getenv("LLM_PROVIDER") or "auto").lower().strip()
    target_model = model or os.getenv("LLM_MODEL")

    # 1. Explicit Provider Execution (if specified)
    if target_provider == "openai" and (OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")):
        m = target_model or "gpt-4o-mini"
        print(f"[Log] 🤖 Executing requested OpenAI LLM ({m})...")
        try:
            return _call_openai_compatible(
                api_key=OPENAI_API_KEY or os.getenv("OPENAI_API_KEY"),
                base_url=(base_url or os.getenv("LLM_BASE_URL") or "https://api.openai.com/v1/chat/completions"),
                model=m, prompt=prompt, system_prompt=system_prompt, max_tokens=max_tokens, temperature=temperature, timeout=timeout
            )
        except Exception as e:
            print(f"[Warning] OpenAI LLM failed: {e}. Proceeding to fallbacks...")

    if target_provider in ["anthropic", "claude"] and (ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY")):
        m = target_model or "claude-3-5-haiku-20241022"
        print(f"[Log] 🤖 Executing requested Anthropic Claude LLM ({m})...")
        try:
            return _call_anthropic(
                api_key=ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY"),
                model=m, prompt=prompt, system_prompt=system_prompt, max_tokens=max_tokens, temperature=temperature, timeout=timeout
            )
        except Exception as e:
            print(f"[Warning] Anthropic LLM failed: {e}. Proceeding to fallbacks...")

    if target_provider == "deepseek" and (DEEPSEEK_API_KEY or os.getenv("DEEPSEEK_API_KEY")):
        m = target_model or "deepseek-chat"
        print(f"[Log] 🤖 Executing requested DeepSeek LLM ({m})...")
        try:
            return _call_openai_compatible(
                api_key=DEEPSEEK_API_KEY or os.getenv("DEEPSEEK_API_KEY"),
                base_url="https://api.deepseek.com/chat/completions",
                model=m, prompt=prompt, system_prompt=system_prompt, max_tokens=max_tokens, temperature=temperature, timeout=timeout
            )
        except Exception as e:
            print(f"[Warning] DeepSeek LLM failed: {e}. Proceeding to fallbacks...")

    if target_provider == "groq" and (GROQ_API_KEY or os.getenv("GROQ_API_KEY")):
        m = target_model or "llama-3.3-70b-versatile"
        print(f"[Log] 🤖 Executing requested Groq LLM ({m})...")
        try:
            return _call_openai_compatible(
                api_key=GROQ_API_KEY or os.getenv("GROQ_API_KEY"),
                base_url="https://api.groq.com/openai/v1/chat/completions",
                model=m, prompt=prompt, system_prompt=system_prompt, max_tokens=max_tokens, temperature=temperature, timeout=timeout
            )
        except Exception as e:
            print(f"[Warning] Groq LLM failed: {e}. Proceeding to fallbacks...")

    if target_provider in ["openrouter", "custom"]:
        m = target_model or "meta-llama/llama-3.3-70b-instruct"
        b_url = base_url or os.getenv("LLM_BASE_URL") or "https://openrouter.ai/api/v1/chat/completions"
        key = os.getenv("LLM_API_KEY") or OPENROUTER_API_KEY or os.getenv("OPENROUTER_API_KEY") or "sk-dummy"
        print(f"[Log] 🤖 Executing Custom/OpenRouter API ({m})...")
        try:
            return _call_openai_compatible(
                api_key=key, base_url=b_url, model=m, prompt=prompt, system_prompt=system_prompt, max_tokens=max_tokens, temperature=temperature, timeout=timeout
            )
        except Exception as e:
            print(f"[Warning] Custom/OpenRouter LLM failed: {e}. Proceeding to fallbacks...")

    # 2. Gemini API Fallback Chain
    force_ollama = os.getenv("FORCE_OLLAMA", "").lower() in ["1", "true", "yes"] or target_provider == "ollama"
    if not force_ollama and (GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")):
        g_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
        if target_provider == "gemini" and target_model:
            gemini_models = [target_model, "gemini-3.6-flash", "gemini-flash-lite-latest", "gemini-flash-latest", "gemini-pro-latest"]
        else:
            gemini_models = ["gemini-3.6-flash", "gemini-flash-lite-latest", "gemini-flash-latest", "gemini-pro-latest"]

        # Deduplicate preserving order
        gemini_models = list(dict.fromkeys(gemini_models))

        for g_model in gemini_models:
            max_attempts = 4
            for attempt in range(max_attempts):
                try:
                    if attempt > 0:
                        backoff = min(30, (2 ** attempt) + random.uniform(0.5, 1.5))
                        print(f"[Log] Retrying Gemini API ({g_model}) attempt {attempt+1}/{max_attempts} after {backoff:.1f}s backoff...")
                        time.sleep(backoff)
                    else:
                        print(f"[Log] Attempting Gemini API ({g_model})...")

                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent"
                    headers = {
                        "Content-Type": "application/json",
                        "x-goog-api-key": g_key
                    }
                    gen_config = {"temperature": temperature, "maxOutputTokens": max_tokens}
                    # Omit responseMimeType on retries if server 5xx errors occurred
                    if attempt < 2:
                        gen_config["responseMimeType"] = "application/json"

                    payload = {
                        "contents": [{"role": "user", "parts": [{"text": f"System instructions:\n{system_prompt}\n\nPrompt:\n{prompt}"}]}],
                        "generationConfig": gen_config
                    }
                    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
                    
                    if response.status_code in [429, 500, 502, 503, 504, 529]:
                        print(f"[Warning] Gemini API ({g_model}) returned transient status HTTP {response.status_code}. Retrying...")
                        if attempt < max_attempts - 1:
                            continue

                    response.raise_for_status()
                    res_json = response.json()
                    content = res_json["candidates"][0]["content"]["parts"][0]["text"]
                    print(f"[Log] Gemini API success with {g_model}!")
                    return content
                except Exception as e:
                    err_msg = str(e)
                    if "404" in err_msg or "401" in err_msg or "403" in err_msg:
                        print(f"[Warning] Gemini API ({g_model}) client error: {e}")
                        break
                    if attempt == max_attempts - 1:
                        print(f"[Warning] Gemini API ({g_model}) failed after {max_attempts} attempts: {e}")


    # 3. DeepSeek Fallback
    if (DEEPSEEK_API_KEY or os.getenv("DEEPSEEK_API_KEY")) and target_provider == "auto":
        try:
            print(f"[Log] Fallback: Attempting DeepSeek LLM (deepseek-chat)...")
            return _call_openai_compatible(
                api_key=DEEPSEEK_API_KEY or os.getenv("DEEPSEEK_API_KEY"),
                base_url="https://api.deepseek.com/chat/completions",
                model=target_model or "deepseek-chat",
                prompt=prompt, system_prompt=system_prompt, max_tokens=max_tokens, temperature=temperature, timeout=timeout
            )
        except Exception as e:
            print(f"[Warning] DeepSeek fallback failed: {e}")

    # 4. OpenAI Fallback
    if (OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")) and target_provider == "auto":
        try:
            print(f"[Log] Fallback: Attempting OpenAI LLM (gpt-4o-mini)...")
            return _call_openai_compatible(
                api_key=OPENAI_API_KEY or os.getenv("OPENAI_API_KEY"),
                base_url="https://api.openai.com/v1/chat/completions",
                model=target_model or "gpt-4o-mini",
                prompt=prompt, system_prompt=system_prompt, max_tokens=max_tokens, temperature=temperature, timeout=timeout
            )
        except Exception as e:
            print(f"[Warning] OpenAI fallback failed: {e}")

    # 5. Local LLM (Ollama) Fallback
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    if LOCAL_LLM_URL:
        try:
            print(f"[Log] Attempting local LLM at {LOCAL_LLM_URL}...")
            ollama_model = target_model if target_provider == "ollama" and target_model else LOCAL_LLM_MODEL
            payload = {
                "model": ollama_model,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": min(max_tokens, 32768),
                    "num_ctx": 32768
                }
            }

            ollama_timeout = min(timeout, 12) if timeout else 12
            response = requests.post(LOCAL_LLM_URL, json=payload, timeout=ollama_timeout)
            response.raise_for_status()

            try:
                data = response.json()
                msg = data.get("message", {})
                content = msg.get("content") or msg.get("thinking") or ""
                if not content:
                    raise ValueError("Empty content in response json")
            except Exception as json_err:
                lines = response.text.strip().split('\n')
                content_parts = []
                thinking_parts = []
                for line in lines:
                    try:
                        temp = json.loads(line)
                        msg = temp.get("message", {})
                        c = msg.get("content", "")
                        th = msg.get("thinking", "")
                        if c: content_parts.append(c)
                        if th: thinking_parts.append(th)
                    except Exception:
                        continue
                
                final_text = "".join(content_parts).strip()
                if not final_text:
                    final_text = "".join(thinking_parts).strip()

                if final_text:
                    data = {"message": {"content": final_text}}
                else:
                    raise RuntimeError(f"Ollama returned empty response. Output: {response.text[:200]}") from json_err

            content = data["message"]["content"]
            print(f"[Log] Local LLM ({ollama_model}) success!")
            return content

        except Exception as e:
            print(f"[Info] Local LLM failed: {e}")

    # 6. HuggingFace fallback
    if HF_API_KEY:
        try:
            print(f"[Log] Fallback: Attempting HuggingFace API...")
            url = "https://router.huggingface.co/v1/chat/completions"
            headers = {"Authorization": f"Bearer {HF_API_KEY}", "Content-Type": "application/json"}
            payload = {"model": target_model or "meta-llama/Llama-3.1-8B-Instruct", "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
            response = requests.post(url, headers=headers, json=payload, timeout=min(timeout, 30))
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[Warning] HuggingFace API failed: {e}")

    raise RuntimeError("All configured LLM providers failed. Check API keys or local Ollama service status.")

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
    return isinstance(data, dict) and "question" in data and ("answer" in data or "hint" in data)


def validate_funny_explainer(data):
    if not isinstance(data, dict):
        return False
    if "hook" not in data or "scene_steps" not in data:
        return False
    steps = data.get("scene_steps", [])
    if not isinstance(steps, list) or len(steps) < 2:
        return False
    for step in steps:
        if not isinstance(step, dict) or "text" not in step:
            return False
    return True

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

    # Check for LaTeX macro backslashes inside Text() strings (e.g., \Psi, \theta, \rangle)
    import re
    if re.search(r'\\(Psi|psi|theta|Theta|alpha|beta|gamma|lambda|sigma|omega|rangle|langle|sqrt|frac|int|sum)', code):
        print("[Log] Validation failed: code contains raw LaTeX backslash commands inside Text().")
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

def generate_manim_script(topic, extract_mode="shorts", target_duration=30):
    """
    Generates a Manim CE Python script for an educational explainer.
    Supports extract_mode='shorts' (vertical 9:16 format) or 'long' (horizontal 16:9 format).
    Returns: {"title": str, "code": str, "voiceover_text": str}
    """
    is_shorts = (extract_mode == "shorts")
    layout_instructions = """11. VERTICAL SHORTS LAYOUT (9:16 ASPECT RATIO):
    - This video is formatted for YouTube Shorts / Reels / TikTok (9:16 vertical screen).
    - Visible screen coordinate bounds: x is narrow [-3.8, 3.8], y is tall [-6.5, 6.5].
    - Title MUST be pinned at top: `title.to_edge(UP, buff=0.6)`. All other elements MUST be placed BELOW the title (`next_to(title, DOWN, buff=0.8)` or `y <= 3.5`) so NOTHING collides with the title!
    - Stack all titles, diagrams, text, and labels VERTICALLY from top to bottom (e.g. `VGroup(...).arrange(DOWN, buff=0.5)`).
    - Keep text font sizes modest (e.g., font_size=24-28 for descriptions, font_size=32-38 for main titles) so text never clips or overlaps container boxes.""" if is_shorts else """11. HORIZONTAL WIDESCREEN LAYOUT (16:9 ASPECT RATIO):
    - This video is formatted for traditional 16:9 widescreen display.
    - Screen bounds: x [-6.5, 6.5], y [-3.8, 3.8]. Utilize horizontal space cleanly."""

    # Scoped to Science, Math, Aptitude & Physics (e.g. Theory of Relativity, Calculus, Speed-Distance, etc.)
    scope_directive = """SCOPE & TOPIC DIVERSITY:
- You MUST dynamically select a specific, singular, and mind-blowing concept strictly within SCIENCE (Physics, Theory of Relativity, Quantum Mechanics, Astrophysics), MATHEMATICS (Calculus, Geometry, Probability, Linear Algebra), or APTITUDE & LOGIC (Relative Speed, Work & Time, Permutations, Logic Puzzles).
- Examples of topics you can choose from dynamically include: Einstein's Theory of Relativity, Time Dilation, Quantum Tunneling, Pythagorean Theorem, Derivatives in Calculus, Relative Speed Aptitude, Monty Hall Paradox, etc.
- Pick a NEW, unique topic dynamically every single time. DO NOT pick a generic top-level category name."""

    prompt = f"""Generate a Manim Community Edition (manim) Python script explaining a HIGHLY SPECIFIC, mind-blowing concept related to: {topic}. 

{scope_directive}

REQUIREMENTS:
1. DO NOT explain a broad category. Pick one very specific, singular mathematical, physical, or aptitude concept/equation/paradox within Science, Maths, or Aptitude.
2. The script MUST contain a single class inheriting from Scene named ExplainerScene (e.g. `class ExplainerScene(Scene):`).
3. Use Manim CE syntax (e.g., `self.play(Create(...))`, `self.play(Write(...))`, `self.play(Transform(...))`).
4. CRITICAL PLAIN TEXT ONLY (NO LATEX/GREEK MACROS):
   - DO NOT use `Tex()` or `MathTex()`. The system does NOT have LaTeX installed.
   - You MUST use standard `Text("your text")` for all text, labels, numbers, and equations.
   - DO NOT use LaTeX backslash macros or special math symbols (e.g. DO NOT write `\\Psi`, `\\theta`, `\\rangle`, `\\langle`). Write plain English words instead, such as `Text("Psi")`, `Text("State Psi")`, `Text("Theta")`, `Text("E = mc^2")`, or `Text("a^2 + b^2 = c^2")`.
5. CRITICAL LAYOUT & OVERLAP PREVENTION:
   - Always pin the main Title to the top: `title.to_edge(UP, buff=0.6)`.
   - Place all boxes, labels, and diagrams cleanly BELOW the title (`buff >= 0.8`). Never overlap title text!
   - When surrounding text with rectangles or boxes, use `SurroundingRectangle(..., buff=0.25)` or place labels above/below boxes (`.next_to(box, UP, buff=0.3)`) so text strings NEVER intersect box borders!
   - Break long sentences into multiple small `Text()` lines stacked vertically (`.next_to(..., DOWN, buff=0.2)`).
6. Keep the animation clean, professional, and visually engaging (20-30 seconds). Focus on clear geometric figures, equations, and labels.
7. GEOMETRIC ACCURACY FOR TOPICS:
   - If the topic is 'Pythagorean Theorem' or related to right triangles:
     * You MUST draw a clear right-angled triangle first using `Polygon` (e.g. `Polygon([-2, -1, 0], [1, -1, 0], [1, 1.25, 0], color=BLUE)` where the legs meet at a 90-degree right angle).
     * DO NOT draw just a square or rectangle as the primary subject. The right-angled triangle with legs 'a', 'b' and hypotenuse 'c' MUST be the central visual element.
     * Optionally add squares attached to the sides a, b, and c to visually illustrate a² + b² = c², or highlight the sides and show the formula `Text("a² + b² = c²")`.
   - For all geometry topics, ensure the shapes accurately represent the math principles being taught.
8. Include a complete, clear, multi-sentence voiceover script ("voiceover_text") that thoroughly explains the topic from start to finish. The script MUST end with proper punctuation (period, exclamation mark).
9. CRITICAL TIMING: The voiceover script MUST take exactly {target_duration} seconds to read aloud at a normal speaking pace (approximately {int(target_duration * 2.5)} words). Count your words!
10. Do NOT include markdown blocks in the "code" field. The "code" field MUST be valid raw Python code starting with `from manim import *`.
11. CRITICAL SYNTAX: When creating polygons or lines, use 3D coordinates as lists. Correct: `Polygon([-3, 0, 0], [0, 0, 0], [0, 4, 0])`. Incorrect: `Polygon([(-3, 0), (0, 0)])`.
12. CRITICAL SPACING: DO NOT let text or shapes overlap! Use `.next_to()`, `.shift()`, or `VGroup(...).arrange(...)` to spread items out cleanly across the screen.
13. MANIM COLORS: Use standard Manim color constants like `BLUE`, `TEAL`, `GREEN`, `YELLOW`, `RED`, `PURPLE`, `ORANGE`, `GOLD`, `WHITE`, `GRAY`, `PINK`, or hex strings (e.g. `"#00FFFF"`). DO NOT use `CYAN` (use `TEAL` or `"#00FFFF"`) or `MAGENTA` (use `PINK` or `"#FF00FF"`).
{layout_instructions}

Format as JSON ONLY:
{{
  "title": "Title of the explainer",
  "code": "from manim import *\\n\\nclass ExplainerScene(Scene):\\n    def construct(self):\\n        ...",
  "voiceover_text": "The complete voiceover script to be spoken during this animation."
}}
"""

    def llm_call(attempt):
        response_text = get_llm_response(prompt, temperature=0.7, max_tokens=8192)
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
    # 2. Fix unescaped newlines/tabs inside strings (properly skipping escaped quotes \")
    def fix_whitespace(m):
        return m.group(0).replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    s = re.sub(r'"(?:[^"\\]|\\.)*?"', fix_whitespace, s, flags=re.DOTALL)
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

    # Strip reasoning <think>...</think> blocks from models like Qwen3 / DeepSeek-R1
    output = re.sub(r'<think>.*?</think>', '', output, flags=re.DOTALL).strip()
    if not output: return None

    def try_parse(candidate):
        if not candidate: return None
        try:
            return json.loads(candidate)
        except Exception:
            pass
        try:
            return json.loads(_clean_json_string(candidate))
        except Exception:
            pass
        return None

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

    known_keys = ["emojis", "answer", "script", "title", "story", "facts", "question", "options", "quote", "author", "highlights", "segments", "hint", "hook", "loop_lead"]

    # strategy 1: Prioritized Key-Matching (Find balanced JSON object containing valid schema keys)
    for i in range(len(output)):
        if output[i] == '{':
            candidate = get_balanced(output[i:])
            if candidate:
                obj = try_parse(candidate)
                if isinstance(obj, dict) and any(k in obj for k in known_keys):
                    return obj

    # strategy 2: Direct Balanced Clean & Parse Fallback
    json_candidate = get_balanced(output)
    if json_candidate:
        obj = try_parse(json_candidate)
        if obj is not None:
            return obj
            
    # strategy 3: Greedy Recovery (for Fragmented or Large Lists)
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
        return collected_objects[0] if len(collected_objects) == 1 else collected_objects

    # strategy 3: Key-Value Regex Extractor (for JSON objects with minor syntax flaws)
    extracted_kv = {}
    known_keys = ["emojis", "answer", "hint", "script", "title", "story", "hook", "loop_lead", "question", "options", "quote", "author"]
    for key in known_keys:
        m = re.search(r'"' + key + r'"\s*:\s*"([^"]*)"', output)
        if not m:
            m = re.search(r'"' + key + r'"\s*:\s*"(.*?)"(?=[,\s\}])', output, re.DOTALL)
        if m:
            extracted_kv[key] = m.group(1).replace('\\"', '"').strip()

    if extracted_kv and len(extracted_kv) >= 2:
        print(f"[Log] Extracted {len(extracted_kv)} key-value fields via Regex.")
        return extracted_kv

    # strategy 4: Regex Timestamp/Segment Recovery (Only for Video Clipping / Slicer Outputs)
    if any(k in output.lower() for k in ['"highlights"', '"segments"', '"viral_score"', '"start"', '"end"', 'timestamp']):
        print("[Log] Attempting Regex timestamp segment recovery...")
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
    
    # strategy 5: Emergency Plaintext Fallback
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

def get_sub_topic(category, is_explainer=False):
    """
    Returns a granular sub-topic for a given category to ensure LLM variety.
    If is_explainer is True, returns topics specifically suited for Manim visual animations (Math, Physics, CS).
    """
    if is_explainer:
        # Do not hardcode lists of topics to prevent repetition.
        # Returning the category allows the LLM to dynamically choose a unique subtopic on every run.
        return category



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
        response_text = get_llm_response(prompt, temperature=0.2, max_tokens=1500)
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

def normalize_emoji_guess(data):
    if not isinstance(data, dict):
        return None
    # Check if payload is wrapped inside a top-level key like {"puzzle": {...}}
    for v in data.values():
        if isinstance(v, dict) and (v.get("emojis") or v.get("emoji")) and (v.get("answer") or v.get("movie") or v.get("title")):
            data = v
            break

    emojis = data.get("emojis") or data.get("emoji") or data.get("icon") or data.get("icons")
    answer = data.get("answer") or data.get("movie") or data.get("character") or data.get("title") or data.get("name")
    script = data.get("script") or data.get("voiceover") or data.get("text") or data.get("speech")
    hint = data.get("hint") or data.get("category") or data.get("clue") or "Guess the item!"

    if emojis and answer and script:
        title_str = f"GUESS THE {str(hint).upper()} 🧩" if hint else "GUESS THE EMOJI 🧩"
        return {
            "emojis": str(emojis).strip(),
            "answer": str(answer).strip(),
            "hint": str(hint).strip(),
            "script": str(script).strip(),
            "title": title_str
        }
    return None

def validate_emoji_guess(data):
    return normalize_emoji_guess(data) is not None


def generate_emoji_guess(category="movies", max_tokens=600):
    """
    Generates an Emoji Guess puzzle (Movie, Character, Song, or Pop Culture item).
    Returns: {"emojis": str, "answer": str, "hint": str, "script": str}
    """
    selected_sub = get_sub_topic(category) if category else "movies"
    prompt = f"""Generate a highly engaging "Guess from Emojis" video puzzle for category: {selected_sub}.
REQUIREMENTS:
1. Provide 2 to 4 emojis that cleverly represent a famous Movie, TV Show, Video Game, Song, or Pop Culture Character.
2. The answer must be universally recognizable and fun to guess.
3. Include a short 1-line category hint (e.g. "Disney Animated Movie" or "Blockbuster Sci-Fi").
4. CRITICAL: Do NOT state or reveal the answer in the voiceover script!
5. End the voiceover script with an urgent call-to-action asking viewers to type their answer in the comments section!

JSON Structure ONLY:
{{
  "emojis": "🦁 👑 🌅",
  "answer": "The Lion King",
  "hint": "Disney Classic Movie",
  "script": "Can you guess this movie from these emojis? You have 5 seconds on the clock! Write your answer in the comments right now! No cheating!"
}}
"""
    def llm_call(attempt):
        response_text = get_llm_response(prompt, temperature=0.7, max_tokens=max_tokens)
        data = robust_json_parse(response_text)
        if isinstance(data, list) and len(data) > 0:
            for item in data:
                norm = normalize_emoji_guess(item)
                if norm: return norm
            return normalize_emoji_guess(data[0]) or data[0]
        return normalize_emoji_guess(data) or data

    try:
        res = with_best_of_n(llm_call, validate_emoji_guess, n=3)
        normalized = normalize_emoji_guess(res)
    except Exception as e:
        print(f"[Warning] LLM generation failed for EMOJI_GUESS ({e}). Using fallback puzzle.")
        normalized = None

    if not normalized:
        fallbacks = [
            {"emojis": "🦁 👑 🌅", "answer": "The Lion King", "hint": "Disney Classic Movie", "script": "Can you guess this movie from these emojis? You have 5 seconds on the clock! Write your answer in the comments right now! No cheating!"},
            {"emojis": "🕷️ 🧍 🏙️", "answer": "Spider-Man", "hint": "Superhero Movie", "script": "Guess the superhero movie from these emojis! You have 5 seconds! Type your answer now!"},
            {"emojis": "🚢 🧊 💔", "answer": "Titanic", "hint": "Romance & Drama", "script": "Can you guess this legendary movie from these emojis? 5 seconds on the clock! Comment before time runs out!"},
            {"emojis": "🧙 🧹 ⚡", "answer": "Harry Potter", "hint": "Fantasy Movie", "script": "Guess this magical movie from the emojis! 5 seconds on the clock! Drop your answer in the comments!"}
        ]
        normalized = random.choice(fallbacks)

    ans_safe = str(normalized.get('answer')).encode('ascii', 'ignore').decode('ascii')
    print(f"[Log] EMOJI_GUESS generated answer (hidden in audio): {ans_safe}")
    return normalized


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

    try:
        return with_best_of_n(llm_call, validate_riddle, n=3)
    except Exception as e:
        print(f"[Warning] Riddle LLM failed ({e}). Using fallback riddle.")
        return {
            "question": "I have cities, but no houses. I have mountains, but no trees. I have water, but no fish. What am I?",
            "hint": "Navigation",
            "answer": "A Map",
            "hook": "GENIUS TEST! 🧠",
            "search_term": "world map globe"
        }

def generate_funny_explainer_script(scene_prompt=None, vibe="sarcastic", target_duration=30):
    """
    Generates a sarcastic, hilarious scene breakdown short script with timestamped SFX triggers and visual prompts.
    """
    if not scene_prompt:
        scene_prompt = "Why cats knock glasses off tables at 3 AM"

    system_prompt = (
        "You are an elite viral comedy writer, roast master, and sarcastic pop-culture commentator (in the style of Ryan Reynolds, Screen Rant Pitch Meetings, and Honest Trailers). "
        "Your superpower is taking video clips, TV show scenes, or awkward moments and writing sharp, hilarious, absurd, and extremely sarcastic commentaries that make audiences burst out laughing. "
        "DO NOT write generic corporate summaries or plain factual text. Roast character actions, highlight awkward body language, use absurd metaphors, and deliver top-tier comedy punchlines."
    )

    prompt = f"""Break down this entire video scene/scenario in an extremely funny, sarcastic, and roast-heavy way for a 30-60 second viral video Short.

Video Context:
"{scene_prompt}"

Vibe: {vibe} (heavy sarcasm, hilarious roasts, dry humor, witty, absurd exaggeration)

CRITICAL REQUIREMENT:
Your breakdown MUST cover the FULL story arc of the video:
- Step 1: The setup/beginning of the video.
- Step 2-3: The escalation/middle of the video.
- Step 4: The final climax/resolution/ending of the video.

Respond strictly with a valid JSON object matching this structure:
{{
  "title": "<Short punchy title with emoji>",
  "hook": "<Catchy opening sarcastic question or statement that grabs attention in 2 seconds>",
  "scene_steps": [
    {{
      "step_title": "<Phase 1 name>",
      "text": "<Hilarious 1-2 sentence sarcastic roast line for phase 1>",
      "visual_prompt": "<Specific Pexels or image prompt describing what visual to show>",
      "sound_effect": "VINE_BOOM",
      "sarcastic_note": "<Short punchy 2-4 word sarcastic overlay comment>"
    }},
    {{
      "step_title": "<Phase 2 name>",
      "text": "<Hilarious 1-2 sentence sarcastic roast line for phase 2>",
      "visual_prompt": "<Specific Pexels or image prompt describing what visual to show>",
      "sound_effect": "WHOOSH",
      "sarcastic_note": "<Short punchy 2-4 word sarcastic overlay comment>"
    }},
    {{
      "step_title": "<Phase 3 name>",
      "text": "<Hilarious 1-2 sentence sarcastic roast line for phase 3>",
      "visual_prompt": "<Specific Pexels or image prompt describing what visual to show>",
      "sound_effect": "RECORD_SCRATCH",
      "sarcastic_note": "<Short punchy 2-4 word sarcastic overlay comment>"
    }}
  ],
  "outro": "<Final sarcastic punchline or CTA>"
}}
"""

    def llm_call(attempt):
        response_text = get_llm_response(prompt, system_prompt=system_prompt, max_tokens=1024, temperature=0.85)
        return robust_json_parse(response_text)

    parsed = with_best_of_n(llm_call, validate_funny_explainer, n=3)
    if not parsed:
        parsed = {
            "title": f"Scene Breakdown: {scene_prompt[:25]} 😼",
            "hook": f"Let's break down the sheer genius behind '{scene_prompt}' with zero filter.",
            "scene_steps": [
                {
                    "step_title": "Phase 1: The Setup",
                    "text": "It all begins with innocent intentions right before absolute chaos erupts.",
                    "visual_prompt": f"{scene_prompt} funny setup moment",
                    "sound_effect": "VINE_BOOM",
                    "sarcastic_note": "A masterpiece of bad decisions."
                },
                {
                    "step_title": "Phase 2: Point of No Return",
                    "text": "Physics surrenders and gravity takes over while everyone pretends everything is fine.",
                    "visual_prompt": f"{scene_prompt} chaos climax funny",
                    "sound_effect": "WHOOSH",
                    "sarcastic_note": "Newton would be proud."
                },
                {
                    "step_title": "Phase 3: The Aftermath",
                    "text": "The dust settles, zero lessons are learned, and it will happen again tomorrow.",
                    "visual_prompt": f"{scene_prompt} aftermath reaction meme",
                    "sound_effect": "RECORD_SCRATCH",
                    "sarcastic_note": "10 out of 10 performance."
                }
            ],
            "outro": "Follow for more highly scientific breakdowns of human and animal behavior."
        }

    return parsed

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





def analyze_photo_story_with_vision(photo_paths, user_prompt=None):
    """
    Uses Gemini Multimodal Vision API to visually analyze a list of photo paths.
    Returns structured JSON containing:
    - 'ordered_indices': Best narrative story sequence e.g. [2, 0, 4, 1, 3]
    - 'photo_energies': List of energy levels ['high', 'medium', 'low', ...]
    - 'captions': Contextual overlay captions per photo (e.g. "Touchdown ✈️", "Golden hour 🌅")
    """
    if not photo_paths:
        return {"ordered_indices": [], "photo_energies": [], "captions": []}

    import base64
    from io import BytesIO
    from PIL import Image, ImageOps

    print(f"[Log] 🧠 Initiating Vision LLM analysis on {len(photo_paths)} photos...")
    parts = []
    
    instructions = f"""You are a viral video editor. Analyze these {len(photo_paths)} photos (labeled Image 0 to Image {len(photo_paths)-1}).
    
Goal:
1. Re-order these image indices [0 to {len(photo_paths)-1}] into a narrative story arc (e.g. arrival/setup -> action/climax -> sunset/ending).
2. Classify each image's energy level as "high" (action, dancing, bright colors, expression), "medium", or "low" (scenic, relaxed, dark).
3. Provide a short 1-3 word aesthetic caption with an emoji for each photo (e.g., "Golden Hour 🌅", "City Lights 🌆").

Return JSON ONLY in this exact format:
{{
  "ordered_indices": [0, 1, 2, ...],
  "photo_energies": ["medium", "high", "low", ...],
  "captions": ["Caption 1", "Caption 2", ...]
}}
"""
    parts.append({"text": instructions})

    for i, p in enumerate(photo_paths[:12]):
        try:
            with Image.open(p) as img:
                img = ImageOps.exif_transpose(img)
                img.thumbnail((512, 512))
                buf = BytesIO()
                img.convert("RGB").save(buf, format="JPEG", quality=80)
                b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": b64
                    }
                })
                parts.append({"text": f"Image {i}: {os.path.basename(p)}"})
        except Exception as e:
            print(f"[Warning] Failed to encode photo {p} for Vision LLM: {e}")

    g_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    if g_key:
        for g_model in ["gemini-3.6-flash", "gemini-flash-lite-latest", "gemini-flash-latest"]:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={g_key}"
                headers = {"Content-Type": "application/json"}
                payload = {
                    "contents": [{"role": "user", "parts": parts}],
                    "generationConfig": {"temperature": 0.3, "maxOutputTokens": 800, "responseMimeType": "application/json"}
                }
                res = requests.post(url, headers=headers, json=payload, timeout=30)
                res.raise_for_status()
                raw_text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                data = robust_json_parse(raw_text)
                
                if isinstance(data, dict) and "ordered_indices" in data:
                    print(f"[Log] 🎨 Vision LLM Story Arc analysis complete via {g_model}! Order: {data.get('ordered_indices')}")
                    return data
            except Exception as e:
                print(f"[Warning] Gemini API ({g_model}) failed: {e}")
    else:
        print("[Warning] GEMINI_API_KEY missing for Cloud Vision analysis. Checking local Ollama Vision...")

    # 2. Local Ollama Vision Fallback (llava / qwen2-vl / llama3.2-vision)
    try:
        raw_url = os.getenv("LOCAL_LLM_URL", "http://localhost:11434").rstrip("/")
        if raw_url.endswith("/api/generate") or raw_url.endswith("/api/chat"):
            ollama_chat_url = raw_url.rsplit("/", 1)[0] + "/chat"
        elif raw_url.endswith("/api"):
            ollama_chat_url = f"{raw_url}/chat"
        else:
            ollama_chat_url = f"{raw_url}/api/chat"
        
        b64_images = []
        for p in photo_paths[:8]:
            try:
                with Image.open(p) as img:
                    img = ImageOps.exif_transpose(img)
                    img.thumbnail((512, 512))
                    buf = BytesIO()
                    img.convert("RGB").save(buf, format="JPEG", quality=80)
                    b64_images.append(base64.b64encode(buf.getvalue()).decode("utf-8"))
            except Exception:
                pass

        if b64_images:
            for v_model in ["llava", "qwen2-vl", "llama3.2-vision", LOCAL_LLM_MODEL]:
                try:
                    print(f"[Log] Attempting local Ollama Vision API ({v_model})...")
                    payload = {
                        "model": v_model,
                        "messages": [{
                            "role": "user",
                            "content": instructions,
                            "images": b64_images
                        }],
                        "stream": False,
                        "format": "json"
                    }
                    res = requests.post(ollama_chat_url, json=payload, timeout=45)
                    if res.status_code == 200:
                        raw_text = res.json().get("message", {}).get("content", "")
                        data = robust_json_parse(raw_text)
                        if isinstance(data, dict) and "ordered_indices" in data:
                            print(f"[Log] 🎨 Ollama Vision Story Arc complete via {v_model}! Order: {data.get('ordered_indices')}")
                            return data
                except Exception:
                    pass
    except Exception as e:
        print(f"[Warning] Ollama Vision fallback failed: {e}")

    return {
        "ordered_indices": list(range(len(photo_paths))),
        "photo_energies": ["medium"] * len(photo_paths),
        "captions": [""] * len(photo_paths)
    }

def generate_teach_script(category=None, topic_prompt=None, vibe="upbeat"):
    """
    Generates a structured educational micro-learning script for TEACH mode.
    Supports sub-categories: 'language', 'tech'/'science', 'recipe', 'general'.
    """
    cat = (category or "").lower().strip()
    raw_topic = (topic_prompt or "").strip()

    if any(k in cat or k in raw_topic.lower() for k in ["language", "japanese", "spanish", "french", "german", "italian", "phrase", "word", "vocabulary"]):
        sub_type = "language"
    elif any(k in cat or k in raw_topic.lower() for k in ["recipe", "cooking", "food", "dish", "meal", "pasta", "kitchen"]):
        sub_type = "recipe"
    elif any(k in cat or k in raw_topic.lower() for k in ["tech", "coding", "python", "code", "programming", "science", "math", "developer"]):
        sub_type = "code"
    else:
        sub_type = "general"

    # Auto-pick dynamic topic if none or generic specified
    DEFAULT_TEACH_TOPICS = {
        "language": [
            "Essential Japanese travel phrase (Arigatou Gozaimasu / Otsukaresama)",
            "Useful Spanish greeting (Que tal / Hasta luego)",
            "Polite French dining expression (Bon appetit / S'il vous plait)",
            "Common Italian travel phrase (Grazie mille / Ciao bella)",
            "German compound word of the day (Feierabend / Gemütlichkeit)",
            "Korean daily expression (Daebak / Gamsahamnida)"
        ],
        "recipe": [
            "3-Ingredient Garlic Butter Pasta",
            "5-Minute Chocolate Mug Cake",
            "10-Minute Spicy Chili Oil Noodles",
            "Fluffy Japanese Souffle Pancakes",
            "Crispy Rice Paper Tacos",
            "2-Ingredient Banana Oat Pancakes"
        ],
        "code": [
            "Python List Comprehension trick",
            "JavaScript Optional Chaining (?.) magic",
            "CSS Flexbox centering trick",
            "Git Stash workflow secret",
            "Python dictionary merging with pipe operator"
        ],
        "general": [
            "How rainbows form full 360 degree circles",
            "How active noise-cancelling headphones work",
            "Why the sky turns orange during sunset",
            "Why airplane windows have tiny bleed holes",
            "How GPS satellites calculate your position"
        ]
    }

    if not raw_topic or raw_topic.lower() in ["random", "category", "essential knowledge", "none", "recipe", "language", "tech", "general"]:
        topic = random.choice(DEFAULT_TEACH_TOPICS.get(sub_type, DEFAULT_TEACH_TOPICS["general"]))
        print(f"[Log] [TEACH] Auto-selected topic for category '{sub_type}': '{topic}'")
    else:
        topic = raw_topic

    system_prompt = (
        "You are an elite micro-learning educator and viral content creator. "
        "Your goal is to teach a single concept, phrase, recipe, or tech trick in under 30-45 seconds in a punchy, ultra-clear, and engaging style."
    )

    prompt = f"""Create an engaging educational short video script about: "{topic}" (Category: {sub_type.upper()}).
Vibe: {vibe}

CREATIVE DIRECTIVE:
- If "{topic}" is broad or general (e.g. "recipe", "Japanese", "coding tip"), pick a specific, highly famous, viral, and impressive item (e.g., a specific dish, a specific phrase, or a specific python trick).

Respond strictly with valid raw JSON depending on category:

If sub_type is 'language':
{{
  "type": "language",
  "title": "<Short punchy lesson title with emoji>",
  "hook": "<Viral hook phrase under 8 words>",
  "word_or_phrase": "<Target word/phrase in target language>",
  "original_script": "<Original script/Kanji/Accents if applicable>",
  "phonetic": "<Phonetic pronunciation guide>",
  "translation": "<English translation>",
  "breakdown": ["<Part 1 meaning>", "<Part 2 meaning>"],
  "example_sentence": "<Useful sample sentence>",
  "narrator_script": "<Complete spoken narration text under 60 words>",
  "search_term": "<Visual background video search term>"
}}

If sub_type is 'recipe':
{{
  "type": "recipe",
  "title": "<Short punchy dish title with emoji e.g. 5-Min Garlic Butter Pasta 🍝>",
  "hook": "<Viral mouth-watering hook phrase under 8 words e.g. The easiest 5-minute gourmet pasta!>",
  "dish_name": "<Name of dish>",
  "prep_time": "<Prep time e.g. 5 Mins>",
  "ingredients": ["<Amount + Ingredient 1 e.g. 8 oz Spaghetti>", "<Amount + Ingredient 2 e.g. 4 cloves Garlic>", "<Amount + Ingredient 3 e.g. 4 tbsp Butter>", "<Amount + Ingredient 4 e.g. 1/2 cup Parmesan>"],
  "steps": [
    "<Step 1 action e.g. Boil 8 oz pasta in salted water until al dente>",
    "<Step 2 action e.g. Sauté 4 cloves minced garlic in 4 tbsp butter for 1 min>",
    "<Step 3 action e.g. Toss pasta with garlic butter & parmesan until glossy>"
  ],
  "action_visuals": [
    "<2-3 word search query for step 1 e.g. boiling pasta>",
    "<2-3 word search query for step 2 e.g. sizzling garlic butter>",
    "<2-3 word search query for step 3 e.g. tossing pasta cheese>",
    "<2-3 word search query for final result e.g. plating pasta dish>"
  ],
  "narrator_script": "<The exact spoken step-by-step recipe narration under 60 words. MUST explicitly mention step numbers, ingredients, and exact quantities sequentially so a viewer can follow along spoken and visually! E.g. 'Want 5-minute garlic butter pasta? First, boil 8 ounces of pasta in salted water. Next, sauté 4 cloves of minced garlic in 4 tablespoons of butter until golden. Finally, toss in cooked pasta with fresh parmesan and serve hot!'>",
  "search_term": "<2-3 word main food search term e.g. garlic butter pasta>"
}}

If sub_type is 'code':
{{
  "type": "code",
  "title": "<Short punchy tech tip title with emoji>",
  "hook": "<Viral hook phrase under 8 words>",
  "concept": "<Concept name>",
  "code_snippet": "<Short 1-3 line clean code snippet>",
  "explanation_steps": ["<Key point 1>", "<Key point 2>"],
  "key_takeaway": "<One sentence key takeaway>",
  "narrator_script": "<Complete spoken narration text under 60 words>",
  "search_term": "<Visual background video search term>"
}}

If sub_type is 'general':
{{
  "type": "general",
  "title": "<Short punchy lesson title with emoji>",
  "hook": "<Viral hook phrase under 8 words>",
  "concept": "<Core concept name>",
  "breakdown": ["<Fact/Point 1>", "<Fact/Point 2>", "<Fact/Point 3>"],
  "key_takeaway": "<One sentence key takeaway>",
  "narrator_script": "<Complete spoken narration text under 60 words>",
  "search_term": "<Visual background video search term>"
}}
"""

    def llm_call(attempt=0):
        resp = get_llm_response(prompt, system_prompt=system_prompt, temperature=0.5, max_tokens=600)
        return robust_json_parse(resp)

    def validate_teach(data):
        if not isinstance(data, dict):
            return False
        if "title" not in data or "narrator_script" not in data:
            return False
        return True

    try:
        parsed = with_best_of_n(llm_call, validate_teach, n=3)
        print(f"[Log] [TEACH] Script generated successfully (Type: {parsed.get('type')})")
        return parsed
    except Exception as e:
        print(f"[Warning] TEACH script generation failed: {e}. Using intelligent fallback.")
        if sub_type == "language":
            return {
                "type": "language",
                "title": "Essential Japanese Phrase 🇯🇵",
                "hook": "Want to sound like a local in Japan?",
                "word_or_phrase": "Arigatou Gozaimasu",
                "original_script": "ありがとうございます",
                "phonetic": "Ah-ree-gah-toe Go-zigh-mass",
                "translation": "Thank you very much (polite)",
                "breakdown": ["Arigatou = Thank you", "Gozaimasu = Polite emphasis"],
                "example_sentence": "Arigatou gozaimasu for the delicious food!",
                "narrator_script": "Want to sound polite in Japan? Use Arigatou Gozaimasu. It means thank you very much! Save this for your next trip!",
                "search_term": "tokyo japan street aesthetic"
            }
        elif sub_type == "recipe":
            return {
                "type": "recipe",
                "title": "5-Min Garlic Butter Pasta 🍝",
                "hook": "The easiest 5-minute gourmet pasta!",
                "dish_name": "Garlic Butter Pasta",
                "prep_time": "5 Mins",
                "ingredients": ["8 oz Spaghetti", "4 cloves Garlic, minced", "4 tbsp Butter", "1/2 cup Parmesan", "Fresh Parsley"],
                "steps": [
                    "Boil 8 oz pasta in salted water until al dente",
                    "Sauté 4 cloves minced garlic in 4 tbsp butter",
                    "Toss pasta with garlic butter, parmesan & parsley"
                ],
                "action_visuals": [
                    "boiling pasta",
                    "chopping garlic",
                    "sizzling garlic butter",
                    "tossing pasta cheese",
                    "plating pasta dish"
                ],
                "narrator_script": "Want 5-minute garlic butter pasta? Step 1: Boil 8 ounces of pasta in salted water. Step 2: Sauté 4 cloves of minced garlic in 4 tablespoons of butter for 1 minute. Step 3: Toss the cooked pasta into the garlic butter, top with fresh parmesan, and serve hot!",
                "search_term": "garlic butter pasta"
            }
        elif sub_type == "code":
            return {
                "type": "code",
                "title": "Python One-Liner Trick 🐍",
                "hook": "Stop writing 5-line for loops in Python!",
                "concept": "List Comprehension",
                "code_snippet": "squares = [x**2 for x in range(10)]",
                "explanation_steps": ["Creates a list of squares instantly", "Clean, modern one-liner"],
                "key_takeaway": "Readable and up to 3x faster than standard loops!",
                "narrator_script": "Stop writing long for loops in Python! Use list comprehensions to create clean, high-performance code in one single line.",
                "search_term": "coding matrix technology dark cyber"
            }
        else:
            return {
                "type": "general",
                "title": "How Rainbows Form 🌈",
                "hook": "Ever wonder why rainbows are curved?",
                "concept": "Light Refraction",
                "breakdown": ["Sunlight enters rain droplets", "Light bends & splits into colors", "Reflects at a 42-degree angle"],
                "key_takeaway": "Rainbows are full 360-degree circles cut off by the ground!",
                "narrator_script": "Did you know rainbows are actually full 360-degree circles? We only see arches because the ground blocks the bottom half!",
                "search_term": "rainbow sky nature landscape"
            }

if __name__ == "__main__":
    res = generate_mixed_facts("science")
    print(f"Hook: {res['hook']}")
    for i, f in enumerate(res["facts"]):
        print(f"{i+1}. {f['fact']} (True: {f['truth']})")

def generate_scene_breakdown(script_text, category="general"):
    """
    Analyzes narration script text and breaks it down into sentence beats with concise 2-4 word visual search queries for scene-by-scene media matching.
    """
    if not script_text or not str(script_text).strip():
        return []
        
    prompt = f"""
Analyze the video narration script below and divide it into sentence beats.
For each sentence beat, provide a 2 to 4 word highly descriptive visual search query suitable for searching stock footage or images.

Script:
"{script_text}"

Return raw JSON only in this exact format:
{{
  "scenes": [
    {{
      "sentence": "<exact sentence text>",
      "visual_prompt": "<2-4 word English search term for visual background>"
    }}
  ]
}}
"""
    try:
        response = get_llm_response(prompt, system_prompt="You are a cinematic director. Return raw valid JSON only.")
        data = robust_json_parse(response)
        if isinstance(data, dict) and "scenes" in data and isinstance(data["scenes"], list):
            scenes = data["scenes"]
            if len(scenes) > 0:
                return scenes
    except Exception as e:
        print(f"[Warning] LLM scene breakdown failed: {e}. Falling back to rule-based sentence splitting.")
        
    # Rule-based fallback: split by sentence punctuation (. ! ?)
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', str(script_text)) if s.strip()]
    scenes = []
    stopwords = {"did", "you", "know", "that", "the", "is", "of", "and", "a", "in", "to", "it", "with", "have", "for", "are", "on", "this", "what", "how", "why"}
    for sent in sentences:
        words = [w for w in re.findall(r'\w+', sent.lower()) if w not in stopwords and len(w) > 3]
        query = " ".join(words[:3]) if words else category
        scenes.append({"sentence": sent, "visual_prompt": query or category})
        
    return scenes

def translate_script(script_text, target_lang="es"):
    """
    Translates script narration and context into target language (es, hi, de, fr, ja, pt, etc.) while keeping tone and viral punchiness.
    """
    lang_names = {
        "es": "Spanish", "hi": "Hindi", "de": "German", "fr": "French",
        "ja": "Japanese", "pt": "Portuguese", "zh": "Chinese", "it": "Italian",
        "ru": "Russian", "ko": "Korean", "ar": "Arabic", "en": "English"
    }
    lang_full = lang_names.get(target_lang.lower(), target_lang)
    
    prompt = f"""
Translate the following video narration script into high-retention, punchy {lang_full}.
Maintain viral hooks, natural speech cadence, and spoken language idioms suitable for Voice synthesis.

Original Script:
"{script_text}"

Return raw JSON only: {{"translated_script": "<translated script>", "target_language": "{lang_full}"}}
"""
    try:
        response = get_llm_response(prompt, system_prompt="You are a professional video translator and voice adapter. Return raw JSON only.")
        data = robust_json_parse(response)
        if isinstance(data, dict) and data.get("translated_script"):
            return data["translated_script"]
    except Exception as e:
        print(f"[Warning] Translation LLM failed: {e}")
        
    return script_text

EMOJI_KEYWORD_MAP = {
    "fire": "🔥", "hot": "🔥", "burn": "🔥",
    "money": "💰", "cash": "💰", "dollar": "💵", "rich": "🤑", "bank": "🏦",
    "rocket": "🚀", "space": "🌌", "planet": "🪐", "star": "⭐", "moon": "🌙",
    "mind": "🧠", "brain": "🧠", "think": "💡", "idea": "💡", "smart": "🧠",
    "shock": "😱", "crazy": "🤯", "wild": "🤯", "secret": "🤫", "mystery": "🕵️",
    "time": "⏰", "clock": "⏳", "history": "📜", "year": "📅", "fast": "⚡",
    "robot": "🤖", "ai": "🤖", "tech": "💻", "code": "💻", "future": "🔮",
    "heart": "❤️", "love": "❤️", "king": "👑", "queen": "👑", "winner": "🏆",
    "scary": "👻", "ghost": "👻", "death": "💀", "skull": "💀", "danger": "⚠️",
    "car": "🏎️", "speed": "🏎️", "game": "🎮", "food": "🍕", "earth": "🌍"
}

def extract_caption_emojis(words_list):
    """
    Scans word timestamp objects and attaches relevant animated emoji overlays for key nouns and emotions.
    """
    if not words_list or not isinstance(words_list, list):
        return []
        
    emoji_events = []
    for item in words_list:
        if not isinstance(item, dict) or "word" not in item:
            continue
        w_clean = re.sub(r'[^\w]', '', item["word"].lower())
        if w_clean in EMOJI_KEYWORD_MAP:
            emoji_events.append({
                "emoji": EMOJI_KEYWORD_MAP[w_clean],
                "word": item["word"],
                "start": item.get("start", 0),
                "end": item.get("end", item.get("start", 0) + 0.8)
            })
    return emoji_events

def generate_podcast_script(topic="artificial intelligence"):
    """
    Generates a 2-speaker viral podcast debate or Q&A script (Host vs Guest) with alternating dialogue turns.
    """
    prompt = f"""
Write a viral 45-second 2-speaker podcast debate/dialogue about: "{topic}".
Speaker 1 (Host): Witty, curious, asking punchy questions.
Speaker 2 (Guest): Expert, bold, delivering surprising revelations.

Return raw JSON only:
{{
  "topic": "{topic}",
  "dialogue": [
    {{"speaker": "Host", "text": "<Host line>", "voice_vibe": "curious"}},
    {{"speaker": "Guest", "text": "<Guest line>", "voice_vibe": "expert"}},
    {{"speaker": "Host", "text": "<Host follow-up>", "voice_vibe": "surprised"}},
    {{"speaker": "Guest", "text": "<Guest punchline>", "voice_vibe": "bold"}}
  ]
}}
"""
    try:
        response = get_llm_response(prompt, system_prompt="You are a viral podcast producer. Return raw JSON only.")
        data = robust_json_parse(response)
        if isinstance(data, dict) and "dialogue" in data:
            return data
    except Exception as e:
        print(f"[Warning] Podcast script generation failed: {e}")
        
    return {
        "topic": topic,
        "dialogue": [
            {"speaker": "Host", "text": f"Did you know {topic} is changing everything we know?"},
            {"speaker": "Guest", "text": "It's even bigger than that. Most people have no idea what is coming next."},
            {"speaker": "Host", "text": "Wait, what do you mean by that?"},
            {"speaker": "Guest", "text": "Within 5 years, the entire industry will be completely unrecognizable."}
        ]
    }

def generate_viral_metadata(script_text, category="general"):
    """
    Generates 3 viral YouTube Shorts titles, description with hashtags, and SEO tags.
    """
    prompt = f"""
Analyze the video narration below and create viral social metadata.
Category: {category}
Script: "{script_text[:1000]}"

Return raw JSON only:
{{
  "titles": ["<Title 1 with emoji>", "<Title 2 with emoji>", "<Title 3 with emoji>"],
  "description": "<Punchy 2-line description with 5 viral hashtags>",
  "hashtags": ["#shorts", "#viral", "#fyp", "#trending", "#tech"],
  "seo_tags": ["short video", "viral moment", "explained", "interesting facts"]
}}
"""
    try:
        response = get_llm_response(prompt, system_prompt="You are a social media growth manager. Return raw JSON only.")
        data = robust_json_parse(response)
        if isinstance(data, dict) and "titles" in data:
            return data
    except Exception as e:
        print(f"[Warning] Failed to generate viral metadata: {e}")
        
    return {
        "titles": [f"This Changes Everything About {category.title()}! 😱", f"The Shocking Truth About {category.title()} 🤯", f"Did You Know This About {category.title()}? 🔥"],
        "description": f"Mind-blowing insight into {category}! Subscribe for daily viral shorts. #shorts #viral #fyp #trending #{category.lower().replace(' ', '')}",
        "hashtags": ["#shorts", "#viral", "#fyp", "#trending"],
        "seo_tags": [category, "shorts", "viral video", "facts"]
    }

def generate_top5_script(category="inventions that changed history"):
    """
    Generates a viral Top 5 countdown listicle script (Rank 5 to Rank 1).
    """
    prompt = f"""
Write a viral 45-second Top 5 Countdown short about: "{category}".
Provide ranks from #5 down to #1 (the most mind-blowing item at #1).

Return raw JSON only:
{{
  "title": "Top 5 {category.title()}",
  "hook": "Here are the top 5 {category} of all time!",
  "items": [
    {{"rank": 5, "name": "<Item 5>", "fact": "<1 sentence fact>", "search_term": "<2-3 word visual prompt>"}},
    {{"rank": 4, "name": "<Item 4>", "fact": "<1 sentence fact>", "search_term": "<2-3 word visual prompt>"}},
    {{"rank": 3, "name": "<Item 3>", "fact": "<1 sentence fact>", "search_term": "<2-3 word visual prompt>"}},
    {{"rank": 2, "name": "<Item 2>", "fact": "<1 sentence fact>", "search_term": "<2-3 word visual prompt>"}},
    {{"rank": 1, "name": "<Item 1>", "fact": "<1 sentence mind-blowing fact>", "search_term": "<2-3 word visual prompt>"}}
  ],
  "narrator_script": "<Continuous narration script covering hook, ranks 5 through 1>"
}}
"""
    try:
        response = get_llm_response(prompt, system_prompt="You are a viral listicle video producer. Return raw JSON only.")
        data = robust_json_parse(response)
        if isinstance(data, dict) and "items" in data:
            return data
    except Exception as e:
        print(f"[Warning] Top 5 script generation failed: {e}")
        
    return {
        "title": f"Top 5 {category.title()}",
        "hook": f"Here are the top 5 {category} you need to know about!",
        "items": [
            {"rank": 5, "name": "Item 5", "fact": "Rank 5 starts our list with an unexpected entry.", "search_term": category},
            {"rank": 4, "name": "Item 4", "fact": "Rank 4 changed how experts view this field.", "search_term": category},
            {"rank": 3, "name": "Item 3", "fact": "Rank 3 receives millions of searches every month.", "search_term": category},
            {"rank": 2, "name": "Item 2", "fact": "Rank 2 was almost number one.", "search_term": category},
            {"rank": 1, "name": "Item 1", "fact": "Number one is the undisputed champion of history.", "search_term": category}
        ],
        "narrator_script": f"Here are the top 5 {category}! At number 5, Item 5. At number 4, Item 4. At number 3, Item 3. At number 2, Item 2. And the number 1 undisputed champion is Item 1!"
    }

def generate_chat_story_script(topic="texting wrong number mystery"):
    """
    Generates a viral iMessage/WhatsApp style text message chat story between two characters.
    """
    prompt = f"""
Write a viral 40-second animated text message story about: "{topic}".
Sender 1 (Person A): Suspicious or startled.
Sender 2 (Person B): Mysterious, funny, or shocking.

Return raw JSON only:
{{
  "title": "{topic.title()}",
  "messages": [
    {{"sender": "Alex", "text": "Hey are you home yet?", "is_me": true}},
    {{"sender": "Unknown", "text": "Who is this? Look outside your window right now.", "is_me": false}},
    {{"sender": "Alex", "text": "Wait what?? That's not funny...", "is_me": true}},
    {{"sender": "Unknown", "text": "I'm standing by the blue car. Turn off your lights.", "is_me": false}}
  ],
  "narrator_script": "Hey are you home yet? Who is this? Look outside your window right now. Wait what? That's not funny... I'm standing by the blue car. Turn off your lights."
}}
"""
    try:
        response = get_llm_response(prompt, system_prompt="You are a viral chat story writer. Return raw JSON only.")
        data = robust_json_parse(response)
        if isinstance(data, dict) and "messages" in data:
            return data
    except Exception as e:
        print(f"[Warning] Chat story generation failed: {e}")
        
    return {
        "title": topic.title(),
        "messages": [
            {"sender": "Alex", "text": "Hey are you home yet?", "is_me": True},
            {"sender": "Unknown", "text": "Who is this? Look outside your window right now.", "is_me": False},
            {"sender": "Alex", "text": "Wait what?? That's not funny...", "is_me": True},
            {"sender": "Unknown", "text": "Turn off your lights right now.", "is_me": False}
        ],
        "narrator_script": "Hey are you home yet? Who is this? Look outside your window right now. Wait what? That's not funny... Turn off your lights right now."
    }

def generate_horror_story_script(topic="abandoned cabin in the woods"):
    """Generates chilling, dark creepypasta horror story scripts."""
    prompt = f"""
Write a chilling 45-second horror story / creepypasta about: "{topic}".
Build psychological tension, creepy whispers, and an unexpected scary twist.

Return raw JSON only:
{{
  "title": "THE {topic.upper()} 👁️",
  "narrator_script": "<Chilling 45-second narration with dramatic pauses>",
  "search_term": "dark eerie horror abandoned mist fog"
}}
"""
    try:
        response = get_llm_response(prompt, system_prompt="You are a master horror storyteller. Return raw JSON only.")
        data = robust_json_parse(response)
        if isinstance(data, dict) and "narrator_script" in data:
            return data
    except Exception as e:
        print(f"[Warning] Horror script generation failed: {e}")
        
    return {
        "title": f"THE {topic.upper()} 👁️",
        "narrator_script": f"Deep in the woods, there stands a cabin that no map records. They say if you hear knocking inside... never look through the window.",
        "search_term": "dark eerie horror forest cabin mist"
    }

def generate_true_crime_script(case_topic="unsolved mystery of the missing vessel"):
    """Generates documentary-style true crime case scripts."""
    prompt = f"""
Write a compelling 45-second true crime case summary about: "{case_topic}".
Tone: Serious, documentary narrator, analytical.

Return raw JSON only:
{{
  "title": "UNSOLVED: {case_topic.title()} 🕵️",
  "narrator_script": "<Serious documentary case breakdown script>",
  "search_term": "crime scene investigation evidence dark history"
}}
"""
    try:
        response = get_llm_response(prompt, system_prompt="You are a true crime documentary producer. Return raw JSON only.")
        data = robust_json_parse(response)
        if isinstance(data, dict) and "narrator_script" in data:
            return data
    except Exception as e:
        print(f"[Warning] True crime script generation failed: {e}")
        
    return {
        "title": f"UNSOLVED: {case_topic.title()} 🕵️",
        "narrator_script": f"In 1984, an entire research team vanished without a single trace. Decades later, investigator files revealed one shocking detail that changes everything.",
        "search_term": "crime scene investigation evidence dark history"
    }

def generate_bible_story_script(topic="David and Goliath"):
    """Generates epic painterly historical and biblical narrative scripts."""
    prompt = f"""
Write an epic, inspirational 45-second narrative short about biblical story: "{topic}".
Tone: Cinematic, painterly, awe-inspiring.

Return raw JSON only:
{{
  "title": "{topic.title()} 📜",
  "narrator_script": "<Cinematic historical narrative script>",
  "search_term": "ancient epic cinematic landscape golden hour"
}}
"""
    try:
        response = get_llm_response(prompt, system_prompt="You are a cinematic historical storyteller. Return raw JSON only.")
        data = robust_json_parse(response)
        if isinstance(data, dict) and "narrator_script" in data:
            return data
    except Exception as e:
        print(f"[Warning] Bible story script generation failed: {e}")
        
    return {
        "title": f"{topic.title()} 📜",
        "narrator_script": f"Against an army of giants, one young shepherd stood alone. Armed only with faith and five smooth stones, history was about to be rewritten.",
        "search_term": "ancient epic cinematic landscape golden hour"
    }

def generate_article_summary_script(article_url_or_text):
    """Summarizes any web article URL or raw text into a 45-second punchy narration script."""
    raw_content = article_url_or_text
    if str(article_url_or_text).startswith(("http://", "https://")):
        try:
            r = requests.get(article_url_or_text, timeout=10)
            clean_text = re.sub(r'<[^>]+>', ' ', r.text)
            raw_content = " ".join(clean_text.split()[:1500])
        except Exception as e:
            print(f"[Warning] Failed to fetch article URL ({e}). Using raw input string.")
            
    prompt = f"""
Summarize the key findings from this article into a punchy 45-second YouTube Shorts narration script:
"{raw_content[:2500]}"

Return raw JSON only:
{{
  "title": "<Catchy article title with emoji>",
  "narrator_script": "<Punchy 45-second news/tech summary script>",
  "search_term": "<2-3 word visual prompt>"
}}
"""
    try:
        response = get_llm_response(prompt, system_prompt="You are a viral news summary writer. Return raw JSON only.")
        data = robust_json_parse(response)
        if isinstance(data, dict) and "narrator_script" in data:
            return data
    except Exception as e:
        print(f"[Warning] Article summary failed: {e}")
        
    return {
        "title": "BREAKING SUMMARY 📰",
        "narrator_script": f"Here is what you need to know about this major story: {raw_content[:300]}",
        "search_term": "technology news headline innovation"
    }

def generate_ugc_product_script(product_name="AI Video Generator"):
    """Generates viral TikTok/Reels user-generated marketing & product demo shorts."""
    prompt = f"""
Write a viral 40-second UGC product marketing script for product: "{product_name}".
Structure: Hook Problem ➔ Shocking Solution ➔ Product Demo Benefit ➔ Call-to-Action.

Return raw JSON only:
{{
  "title": "TRY {product_name.upper()} 🚀",
  "narrator_script": "<Punchy high-energy UGC script>",
  "search_term": "modern technology smartphone product aesthetic"
}}
"""
    try:
        response = get_llm_response(prompt, system_prompt="You are a top TikTok UGC creator. Return raw JSON only.")
        data = robust_json_parse(response)
        if isinstance(data, dict) and "narrator_script" in data:
            return data
    except Exception as e:
        print(f"[Warning] UGC script generation failed: {e}")
        
    return {
        "title": f"TRY {product_name.upper()} 🚀",
        "narrator_script": f"If you are still creating content manually in 2026, stop right now. {product_name} lets you generate complete viral shorts in under 60 seconds. Try it out now!",
        "search_term": "modern technology smartphone product aesthetic"
    }



