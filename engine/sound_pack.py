"""Bundled real recordings for GUESS_SOUND (assets/sounds, from Wikimedia Commons; licences in manifest.json)."""
import json
import os

DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sounds")
MIN_DB = -45.0  # quieter than this is treated as silence


def load(directory=None):
    """{label: entry} for the sounds that exist on disk and are audible."""
    d = directory or DIR
    try:
        with open(os.path.join(d, "manifest.json"), "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in raw.items()
            if os.path.exists(os.path.join(d, v.get("file", ""))) and v.get("mean_db", 0) > MIN_DB}


def labels(directory=None):
    return sorted(load(directory))


def match(text, directory=None):
    """Label found in free text ('lion roar' -> 'lion'), longest label first, else None."""
    low = (text or "").lower()
    for label in sorted(load(directory), key=len, reverse=True):
        if label in low:
            return label
    return None


def path(label, directory=None):
    e = load(directory).get(label)
    return os.path.join(directory or DIR, e["file"]) if e else None


def credit(label, directory=None):
    """One line for the video description; empty for CC0 / public domain."""
    e = load(directory).get(label)
    if not e or e.get("license", "").upper() == "CC0" or "public" in e.get("license", "").lower():
        return ""
    who = f" by {e['author']}" if e.get("author") else ""
    return f"Sound: \"{e['title']}\"{who}, {e['license']}, {e['source']}"
