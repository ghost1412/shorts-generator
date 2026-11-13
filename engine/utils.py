import re
import json

def find_fact_start_times(subs_file, num_facts):
    """Spoken start time of each 'Number N.' marker, so background cuts land on each fact."""
    try:
        with open(subs_file, "r", encoding="utf-8") as f:
            words = json.load(f)
        if isinstance(words, dict):
            words = [w for seg in words.get("segments", []) for w in seg.get("words", [])]
        starts = []
        for n in range(1, num_facts + 1):
            targets = {str(n), ["one", "two", "three", "four", "five"][n - 1]}
            for i, w in enumerate(words[:-1]):
                if re.sub(r"[^a-z]", "", w["word"].lower()) == "number" and \
                   re.sub(r"[^a-z0-9]", "", words[i + 1]["word"].lower()) in targets and \
                   (not starts or float(w["start"]) > starts[-1]):
                    starts.append(float(w["start"]))
                    break
        return starts if len(starts) == num_facts else None
    except Exception as e:
        print(f"[Warning] Could not align facts to voice timestamps: {e}")
        return None
