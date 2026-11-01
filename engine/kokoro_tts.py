"""Kokoro text-to-speech: free, local, no API key, runs on CPU (kokoro-onnx, Apache-2.0 model).

    python main.py --mode FACTS --tts_provider kokoro --voice af_heart

Install `pip install kokoro-onnx soundfile`. The int8 model (~90 MB) and voices (~28 MB) download once into
~/.cache/shortsflow/kokoro when --tts_provider kokoro is chosen (set KOKORO_MODEL_DIR to use another folder).
The model has no word timings, so each sentence is synthesised on its own (exact sentence boundaries) and the
words inside it are spread by length, which is accurate enough for caption pop-in.
"""
import json
import os
import re
import subprocess

MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
MODEL_FILE, VOICES_FILE = "kokoro-v1.0.int8.onnx", "voices-v1.0.bin"
DEFAULT_VOICE = "af_heart"
SAMPLE_RATE = 24000
PAUSE_SECONDS = {".": 0.28, "!": 0.28, "?": 0.32, ",": 0.12, ";": 0.15, ":": 0.15}
_VOICE_RE = re.compile(r"^[abefhijpz][fm]_\w+$")  # kokoro voice ids: af_heart, am_michael, bf_emma, ...
_kokoro = None


def model_dir():
    return os.getenv("KOKORO_MODEL_DIR") or os.path.join(os.path.expanduser("~"), ".cache", "shortsflow", "kokoro")


def is_available(download=False):
    """True when kokoro-onnx is installed and the model files are present (or `download` fetches them)."""
    try:
        import kokoro_onnx  # noqa: F401
        import soundfile  # noqa: F401
    except ImportError:
        return False
    folder = model_dir()
    if all(os.path.exists(os.path.join(folder, f)) for f in (MODEL_FILE, VOICES_FILE)):
        return True
    if not download:
        return False
    import requests
    os.makedirs(folder, exist_ok=True)
    for name in (MODEL_FILE, VOICES_FILE):
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            print(f"[Log] Downloading Kokoro {name} (one-time)...")
            with requests.get(MODEL_URL + name, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(path + ".part", "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
            os.replace(path + ".part", path)
    return True


def pick_voice(voice_name=None):
    """Use a Kokoro voice id as-is; anything else (e.g. an edge-tts name) maps to KOKORO_VOICE / af_heart."""
    if voice_name and _VOICE_RE.match(voice_name):
        return voice_name
    return os.getenv("KOKORO_VOICE", DEFAULT_VOICE)


def split_chunks(text):
    """[(chunk_text, trailing_punctuation)] split after . ! ? , ; : so each chunk is synthesised separately."""
    chunks = [m.group(0).strip() for m in re.finditer(r"[^.!?,;:]+[.!?,;:]*|[.!?,;:]+", text)]
    out = []
    for chunk in chunks:
        if not chunk:
            continue
        spoken = re.sub(r"[.!?,;:\s]+$", "", chunk)
        if not re.search(r"\w", spoken):
            continue
        punct = chunk[len(spoken):].strip()[:1]
        out.append((spoken, punct))
    return out


def word_times(text, start, duration):
    """Spread the words of one chunk over [start, start+duration] in proportion to their length."""
    words = text.split()
    if not words:
        return []
    weights = [len(re.sub(r"\W", "", w)) + 1 for w in words]
    total, cursor, out = float(sum(weights)), start, []
    for word, weight in zip(words, weights):
        dur = duration * weight / total
        out.append({"word": word, "start": round(cursor, 3), "end": round(cursor + dur, 3), "duration": round(dur, 3)})
        cursor += dur
    return out


def _engine():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        _kokoro = Kokoro(os.path.join(model_dir(), MODEL_FILE), os.path.join(model_dir(), VOICES_FILE))
    return _kokoro


def generate_voice_kokoro(text, output_audio="assets/voice.mp3", output_subs="assets/subs.json",
                          voice_name=None, speed=1.0, download=True):
    """Synthesise `text` locally. Returns (audio_path, subs_path) like the other voice providers."""
    import numpy as np
    import soundfile as sf
    if not is_available(download=download):
        raise RuntimeError("Kokoro not available: pip install kokoro-onnx soundfile (model downloads on first use)")
    kokoro, voice = _engine(), pick_voice(voice_name)
    print(f"[Log] Generating voice locally via Kokoro (voice: {voice})...")
    chunks = split_chunks(text)
    if not chunks:
        raise ValueError("Kokoro: nothing to speak")

    audio, subtitles, cursor = [], [], 0.0
    for spoken, punct in chunks:
        samples, sr = kokoro.create(spoken, voice=voice, speed=speed, lang="en-us")
        dur = len(samples) / sr
        subtitles += word_times(spoken, cursor, dur)
        audio.append(samples)
        cursor += dur
        pause = PAUSE_SECONDS.get(punct, 0.0)
        if pause:
            audio.append(np.zeros(int(sr * pause), dtype=samples.dtype))
            cursor += pause

    os.makedirs(os.path.dirname(os.path.abspath(output_audio)), exist_ok=True)
    wav = os.path.splitext(output_audio)[0] + ".kokoro.wav"
    sf.write(wav, np.concatenate(audio), SAMPLE_RATE)
    import imageio_ffmpeg
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", wav, "-b:a", "192k", output_audio],
                   capture_output=True, check=True)
    os.remove(wav)
    with open(output_subs, "w", encoding="utf-8") as f:
        json.dump(subtitles, f, indent=2)
    return output_audio, output_subs
