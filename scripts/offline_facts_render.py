"""
Offline FACTS render: runs main.py end to end with a canned LLM response, so rendering,
timing and styling can be checked without any LLM API key (PEXELS_API_KEY still needed).

    python scripts/offline_facts_render.py      # writes sessions/offline_test/interactive_short_*.mp4
"""
import json
import os
import runpy
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import engine.script_gen as sg

CANNED = {
    "hook": "Ancient Rome had one rule nobody believes was real.",
    "facts": [
        {"fact": "Roman emperors once declared war on the sea god Neptune and ordered soldiers to stab the waves.", "truth": True, "visual": "ocean waves crashing"},
        {"fact": "Romans used crushed mouse brains as toothpaste to whiten their teeth.", "truth": True, "visual": "ancient roman ruins"},
        {"fact": "Julius Caesar banned purple togas for everyone except gladiators who won ten fights.", "truth": False, "visual": "purple fabric"},
    ],
    "lie_explanation": "Purple was reserved for emperors and senators, not gladiators.",
    "loop_lead": "Rewatch number two before you answer.",
}

# Every LLM call (script + metadata) gets the canned JSON; metadata then falls back to its default.
sg.get_llm_response = lambda prompt, **kw: json.dumps(CANNED)

os.makedirs("sessions/offline_test", exist_ok=True)
sys.argv = ["main.py", *os.environ.get("OFFLINE_EXTRA_ARGS", "").split(), "--mode", "FACTS", "--category", "history", "--use_remotion",
            "--caption_style", "HORMOZI", "--skip-upload", "--session_dir", "sessions/offline_test"]
runpy.run_path(os.path.join(ROOT, "main.py"), run_name="__main__")
