"""Background footage that fits the story (REDDIT, STORY and other spoken-story modes).

Without this, half of the story backgrounds are a random "satisfying" clip (slime, soap) that has nothing to do with the
story. `pick(text)` reads the title/topic/story words and returns a Pexels search that matches the mood, or None when no
mood is clear (the old behaviour then applies).
"""
import random
import re

MOODS = [
    ("work", {"boss", "office", "coworker", "colleague", "job", "manager", "fired", "salary", "workplace", "interview", "career"},
     ["office desk typing", "busy office people working", "empty office night", "city commuters walking"]),
    ("family", {"wedding", "mother", "father", "mom", "dad", "sister", "brother", "family", "parents", "mother-in-law", "grandma",
                "grandmother", "grandfather", "daughter", "son"},
     ["family dinner table", "cozy living room home", "suburban house street", "old family photos"]),
    ("love", {"girlfriend", "boyfriend", "husband", "wife", "dating", "ex", "cheating", "breakup", "marriage", "relationship", "crush"},
     ["couple walking city night", "rain on window", "empty cafe evening", "sunset city skyline"]),
    ("school", {"school", "teacher", "classmate", "college", "university", "student", "exam", "homework", "professor"},
     ["school hallway", "students walking campus", "classroom desks", "library books"]),
    ("money", {"money", "rich", "poor", "inheritance", "landlord", "rent", "debt", "lottery", "bill", "tip", "bank"},
     ["city street busy", "apartment building exterior", "cash counting", "luxury car street"]),
    ("neighbor", {"neighbor", "neighbour", "roommate", "apartment", "stranger", "fence", "noise", "parking"},
     ["apartment building exterior", "quiet suburban street", "hallway door apartment", "street at night"]),
    ("travel", {"flight", "airport", "trip", "vacation", "hotel", "road", "airplane", "luggage"},
     ["airport terminal people", "road trip driving", "airplane window clouds", "hotel corridor"]),
]


def _words(text):
    return set(re.findall(r"[a-z][a-z-]*", (text or "").lower()))


def mood_of(text):
    """Name of the mood whose keywords appear most in `text`, or None. A tie goes to the earlier entry in MOODS."""
    words = _words(text)
    best, best_hits = None, 0
    for name, keys, _queries in MOODS:
        hits = len(words & keys)
        if hits > best_hits:
            best, best_hits = name, hits
    return best


def pick(text, rng=random):
    """A search query that fits the story's mood, or None when the text has no clear mood."""
    name = mood_of(text)
    if not name:
        return None
    for n, _keys, queries in MOODS:
        if n == name:
            return rng.choice(queries)
    return None
