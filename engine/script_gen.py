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
    for f in facts:
        words = f["fact"].split()
        if len(words) >= 2:
            # First two words usually identify the subject
            subjects.append(" ".join(words[:2]).lower())
    
    # We need 3 unique subjects for 3 facts
    return len(set(subjects)) < 3

def reject_known_false_patterns(facts):
    """Rejects common myths or widely known false facts that LLMs often hallucinate as true."""
    known_myths = [
        "einstein failed math",
        "humans use only 10",
        "napoleon was short",
        "vikings wore horned helmets",
        "tesla invented wifi",
        "goldfish have 3 second memory",
        "great wall visible from moon"
    ]
    for f in facts:
        text = f["fact"].lower()
        for myth in known_myths:
            if myth in text:
                return True
    return False

def enforce_specificity(facts):
    """Ensures all facts contain a verifiable anchor: a number or a proper noun (Name)."""
    for f in facts:
        text = f["fact"]
        # must contain at least one digit or a word starting with uppercase (excluding start of sentence)
        has_number = any(char.isdigit() for char in text)
        words = text.split()
        # Check for capitalized words after the first one to avoid sentence-start false positives
        has_name = any(w[0].isupper() for w in words[1:]) if len(words) > 1 else False
        
        # Also check first word just in case it's a name like "Einstein" (though ambiguous)
        if not (has_number or has_name or (words and words[0][0].isupper())):
            return False
    return True

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

def with_retry(func, validator, max_retries=2, fallback=None):
    """Generic retry wrapper for LLM calls with custom validation."""
    for attempt in range(max_retries + 1):
        try:
            result = func(attempt)
            if validator(result):
                return result
            print(f"⚠️ Attempt {attempt+1}: Validation failed. Retrying...")
        except Exception as e:
            print(f"💡 Attempt {attempt+1} failed ({type(e).__name__}: {e})")
    
    if fallback:
        print("🚨 All retries failed. Using fallback.")
        return fallback()
    raise RuntimeError("LLM generation failed validation after all retries.")

def generate_best_of_3(generator):
    """
    Runs a generator 3 times and picks the one with the highest 'viral score'
    (based on length and punchiness/exclamation).
    """
    results = []
    for _ in range(3):
        try:
            results.append(generator())
        except:
            pass
    
    if not results:
        return generator() # Final attempt if all failed
        
    def score(x):
        text = str(x)
        # Higher score for longer text (substance) + extra points for punchy punctuation
        return len(text) + 12 * text.count("!") + 8 * text.count("?")
    
    best = max(results, key=score)
    print(f"[Log] Best of 3 selected (Score: {score(best)})")
    return best

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
    
    prompt = f"""SPOT THE LIE! 🔍 One of these facts about {selected_sub} is a fake. 

TASK:
Generate EXACTLY 3 facts:
- 2 TRUE (factually correct)
- 1 FALSE (plausible but incorrect)

STRICT RULES (MUST FOLLOW):
1. Each fact must be under 10 words.
2. Total output must be under 40 words.
3. Facts must be specific (include year, name, or detail).
4. NO vague or generic facts.
5. NO TECHNICAL NOISE: Do NOT include URLs, version numbers (e.g., v1.0), or "random script things" like JSON keys.

FACT CREATION PROCESS:
Step 1: Generate 2 obscure TRUE facts about DIFFERENT people/entities.
Step 2: Independently verify both are 100% correct.
Step 3: Take a DIFFERENT REAL fact and alter ONE key detail:
        - year (1964 → 1972)
        - name
        - number
Step 4: Ensure the altered version is FALSE but believable.

CRITICAL DIVERSITY RULES:
- Each fact MUST be about a DIFFERENT person, place, or entity.
- Do NOT repeat the same subject in two different facts (e.g. no "Rock in UH" vs "Rock in USC").
- Diversity is more important than difficulty!

SELF-CHECK BEFORE OUTPUT:
- Identify which fact is false
- Ensure it differs by ONLY ONE detail
- Ensure both true facts are historically accurate
If any condition fails → REGENERATE internally.

OUTPUT FORMAT (JSON ONLY):
{{
  "hook": "5-word curiosity hook",
  "facts": [
    {{"fact": "...", "truth": true}},
    {{"fact": "...", "truth": true}},
    {{"fact": "...", "truth": false}}
  ]
}}
"""
    
    def llm_call(attempt):
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 800,
            "temperature": 0.2
        }
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        output = response.json()["choices"][0]["message"]["content"]
        data = robust_json_parse(output)
        
        # Clean data (prefixes)
        facts_list = data.get("facts", [])
        for f in facts_list:
            f["fact"] = f["fact"].split(": ", 1)[-1] if ": " in f["fact"] else f["fact"]
        data["facts"] = facts_list[:3]
        return data

    def facts_validator(data):
        facts = data.get("facts", [])
        if reject_bad_facts(facts):
            return False
        if reject_duplicates(facts):
            return False
        if reject_same_subject(facts):
            return False
        if reject_known_false_patterns(facts):
            return False
        if not enforce_specificity(facts):
            return False
        if not validate_semantics(facts):
            return False
        return True

    result = with_retry(
        llm_call, 
        facts_validator, 
        fallback=lambda: generate_fallback_facts(category)
    )
    
    # Shuffle for engagement
    random.shuffle(result["facts"])
    return result

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
5. End on a shocking twist or realization.
6. Keep it under 100 words.

CRITICAL VALIDATION:
- Story must be about a REAL documented event.
- Must include at least one verifiable anchor (year, place, or specific person).
- DO NOT fabricate unknown events or use vague terms like "someone" or "somewhere".
- NO TECHNICAL NOISE: Do NOT include URLs, version numbers (e.g., v1.0), or "random script things" like JSON keys.

Format as JSON ONLY:
{{
  "title": "A short viral title with emojis",
  "story": "The full story text starting with the intense hook..."
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

    return with_retry(llm_call, validate_story)

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
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 400,
            "temperature": 0.2
        }
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        output = response.json()["choices"][0]["message"]["content"]
        wyr = robust_json_parse(output)
        if wyr.get("percent_a", 0) + wyr.get("percent_b", 0) != 100:
            wyr["percent_b"] = 100 - wyr.get("percent_a", 50)
        return wyr

    return with_retry(llm_call, validate_wyr)

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
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 600,
            "temperature": 0.2
        }
        response = requests.post(url, headers=headers, json=payload, timeout=25)
        response.raise_for_status()
        output = response.json()["choices"][0]["message"]["content"]
        return robust_json_parse(output)

    return with_retry(llm_call, validate_reddit)

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
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 400,
            "temperature": 0.2
        }
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        output = response.json()["choices"][0]["message"]["content"]
        return robust_json_parse(output)

    return with_retry(llm_call, validate_trivia)

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
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 400,
            "temperature": 0.2
        }
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        output = response.json()["choices"][0]["message"]["content"]
        return robust_json_parse(output)

    return with_retry(llm_call, validate_quote)
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
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 400,
            "temperature": 0.3 if tone == "funny" else 0.2
        }
        response = requests.post(url, headers=api_headers, json=payload, timeout=20)
        response.raise_for_status()
        output = response.json()["choices"][0]["message"]["content"]
        data = robust_json_parse(output)
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

    return with_retry(llm_call, validate_news, fallback=fallback)

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
        payload = {
            "model": "meta-llama/Llama-3.1-8B-Instruct",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 200
        }
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        return robust_json_parse(response.json()["choices"][0]["message"]["content"])

    def fallback():
        return {
            "hook": "Can you guess this sound?",
            "object": "Elephant",
            "sound_query": "elephant trumpeting",
            "reveal_text": "It was an Elephant! Shocking right?"
        }

    return with_retry(llm_call, validate_sound_challenge, fallback=fallback)


if __name__ == "__main__":
    res = generate_mixed_facts("science")
    print(f"Hook: {res['hook']}")
    for i, f in enumerate(res["facts"]):
        print(f"{i+1}. {f['fact']} (True: {f['truth']})")
