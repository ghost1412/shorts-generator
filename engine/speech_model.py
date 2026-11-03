"""Which Whisper model to use, and whether it still has to be downloaded.

`medium` (1.5 GB) gives the best punctuation and is fine on an NVIDIA GPU, but on a CPU it is far too slow for a first
impression, so CPU machines default to `small` (about 460 MB). Override with SHORTSFLOW_WHISPER_MODEL
(tiny, base, small, medium, large-v3).
"""
import os

# approximate download sizes in MB (openai-whisper checkpoints)
MODEL_MB = {"tiny": 75, "base": 145, "small": 465, "medium": 1530, "large": 2900, "large-v3": 2900}


def pick_model(device):
    chosen = (os.getenv("SHORTSFLOW_WHISPER_MODEL") or "").strip()
    if chosen:
        return chosen
    return "medium" if device == "cuda" else "small"


def cache_dir():
    base = os.getenv("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "whisper")


def is_downloaded(name):
    return os.path.exists(os.path.join(cache_dir(), f"{name}.pt"))


def download_notice(name):
    """One log line when the model is not on disk yet, else None. The WebUI turns it into a friendly status message."""
    if is_downloaded(name):
        return None
    mb = MODEL_MB.get(name)
    size = f" (about {mb / 1000:.1f} GB)" if mb and mb >= 1000 else (f" (about {mb} MB)" if mb else "")
    return f"[Log] Downloading the speech model '{name}'{size}, first time only. This can take a few minutes..."
