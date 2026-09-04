import json
import os
import asyncio
import edge_tts
import re
from xml.sax.saxutils import escape as xml_escape

def clean_for_tts(text):
    """
    Strips emojis, URLs, and common web noise while preserving useful symbols.
    """
    if not isinstance(text, str):
        print(f"[Warning] clean_for_tts received non-string ({type(text)}). Converting...")
        text = str(text)
        
    # 1. Strip URLs
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    # 2. Strip standalone domains/versions like example.com or v1.0
    text = re.sub(r'\b\S+\.com\S*|\b\S+\.net\S*|\bv\d+\.\d+\b', '', text)
    
    # 3. Clean up stray punctuation and extra spaces
    text = re.sub(r'\(\s*\)', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    # 4. Strip emojis but keep useful symbols (%, $)
    result = []
    allowed_chars = set(".,!?;:()-'\" %$")
    for c in text:
        if ord(c) < 127:
            if c.isalnum() or c.isspace() or c in allowed_chars:
                result.append(c)
    return "".join(result)

def add_dramatic_pauses(text):
    """Injects punctuation-based breaks that edge-tts naturally interprets."""
    # Strong pause after each point/digit
    text = re.sub(r'(\d+[:\.])\s*', r'\1 ... ', text)
    # Long pause before reveal
    text = re.sub(r'(The real answer is)', r'... \1', text)
    # Natural breathing pauses at sentence ends
    text = re.sub(r'(\.\s+)', r'... ', text)
    # Comma for micro-pauses
    text = re.sub(r',', ', ', text)
    return text

def split_hook(text):
    """Robustly splits text into hook and rest, falling back to first sentence."""
    # Try splitting by first explicit ellipsis
    if "..." in text:
        parts = text.split("...", 1)
        return parts[0].strip(), parts[1].strip()

    # fallback: first sentence as hook
    sentences = re.split(r'[.!?]', text, maxsplit=1)
    if len(sentences) > 1:
        return sentences[0].strip(), sentences[1].strip()

    return text.strip(), ""

def group_subtitles(subtitles):
    """Groups word-by-word subtitles into cleaner, punctuation-aware chunks (opt-in only)."""
    if not subtitles: return []
    grouped = []
    current = []

    for w in subtitles:
        current.append(w)
        word_text = w["word"].strip()
        if any(p in word_text for p in [".", "!", "?"]) or len(current) >= 4:
            grouped.append({
                "word": " ".join([x["word"] for x in current]),
                "start": current[0]["start"],
                "end": current[-1]["start"] + current[-1]["duration"],
                "duration": sum(x["duration"] for x in current)
            })
            current = []

    if current:
        grouped.append({
            "word": " ".join([x["word"] for x in current]),
            "start": current[0]["start"],
            "end": current[-1]["start"] + current[-1]["duration"],
            "duration": sum(x["duration"] for x in current)
        })

    return grouped


def generate_voice_elevenlabs(text, output_audio="assets/voice.mp3", output_subs="assets/subs.json", voice_id=None, api_key=None):
    """
    Generates voice using ElevenLabs API with word-level timestamps.
    Falls back to edge-tts if API key is not available.
    """
    import requests as req_lib

    voice_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")  # Sarah (default)
    api_key = api_key or os.getenv("ELEVENLABS_API_KEY", "")

    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY not set")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.85}
    }

    print(f"[Log] Generating voice via ElevenLabs (voice: {voice_id})...")
    response = req_lib.post(url, json=payload, headers=headers, timeout=60)
    response.raise_for_status()
    data = response.json()

    # Save audio
    import base64
    audio_bytes = base64.b64decode(data["audio_base64"])
    os.makedirs(os.path.dirname(os.path.abspath(output_audio)), exist_ok=True)
    with open(output_audio, "wb") as f:
        f.write(audio_bytes)

    # Build word-level subtitles from alignment data
    subtitles = []
    alignment = data.get("alignment", {})
    chars = alignment.get("characters", [])
    char_starts = alignment.get("character_start_times_seconds", [])
    char_ends = alignment.get("character_end_times_seconds", [])

    current_word = ""
    word_start = None
    for i, (ch, cs, ce) in enumerate(zip(chars, char_starts, char_ends)):
        if ch == " " or i == len(chars) - 1:
            if ch != " " and i == len(chars) - 1:
                current_word += ch
                if word_start is None:
                    word_start = cs
            if current_word.strip():
                duration = max(0.05, ce - word_start)
                subtitles.append({
                    "word": current_word.strip(),
                    "start": round(word_start, 3),
                    "end": round(word_start + duration, 3),
                    "duration": round(duration, 3)
                })
            current_word = ""
            word_start = None
        else:
            if word_start is None:
                word_start = cs
            current_word += ch

    with open(output_subs, "w", encoding="utf-8") as f:
        json.dump(subtitles, f, indent=2)

    print(f"[Log] ElevenLabs: {len(subtitles)} word timestamps saved.")
    return output_audio, output_subs


def generate_voice(text, output_audio="assets/voice.mp3", output_subs="assets/subs.json", voice_name="en-US-AvaNeural", rate="+15%", pitch="+0Hz", add_cta=True, group=False):
    """
    Generates voice with cinematic pacing and word-level subtitle timestamps.
    Uses ElevenLabs if ELEVENLABS_API_KEY is set, otherwise falls back to edge-tts.
    group=False (default): writes individual word timestamps for frame-accurate Remotion captions.
    group=True: merges into 4-word chunks (legacy behaviour).
    """
    # Route to ElevenLabs if API key available
    if os.getenv("ELEVENLABS_API_KEY"):
        try:
            return generate_voice_elevenlabs(
                text=clean_for_tts(text),
                output_audio=output_audio,
                output_subs=output_subs
            )
        except Exception as e:
            print(f"[Warning] ElevenLabs failed ({e}). Falling back to edge-tts.")

    raw_text = clean_for_tts(text)
    
    hook, rest = split_hook(raw_text)
    processed_rest = add_dramatic_pauses(rest or "")
    
    final_text = f"{hook} ... {processed_rest}"
    if add_cta:
        final_text += " ... Comment your answer now."

    os.makedirs(os.path.dirname(os.path.abspath(output_audio)), exist_ok=True)
    
    async def amain():
        communicate = edge_tts.Communicate(final_text, voice_name, rate=rate, pitch=pitch)
        subtitles = []
        
        with open(output_audio, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] in ["WordBoundary", "word_boundary"]:
                    start_sec = chunk["offset"] / 10_000_000
                    dur_sec = max(0.05, chunk["duration"] / 10_000_000)
                    subtitles.append({
                        "word": chunk["text"],
                        "start": round(start_sec, 3),
                        "end": round(start_sec + dur_sec, 3),
                        "duration": round(dur_sec, 3)
                    })
                elif chunk["type"] == "SentenceBoundary":
                    text_chunk = chunk["text"]
                    words = text_chunk.split()
                    if not words: continue
                    
                    sent_start = chunk["offset"] / 10_000_000
                    sent_dur = chunk["duration"] / 10_000_000
                    avg_word_dur = sent_dur / len(words)
                    
                    for i, word in enumerate(words):
                        ws = sent_start + (i * avg_word_dur)
                        subtitles.append({
                            "word": word,
                            "start": round(ws, 3),
                            "end": round(ws + avg_word_dur, 3),
                            "duration": round(max(0.1, avg_word_dur), 3)
                        })

        # Final fallback
        if not subtitles:
            audio_duration = 0
            try:
                try:
                    from moviepy.audio.io.AudioFileClip import AudioFileClip
                except ImportError:
                    from moviepy.editor import AudioFileClip
                ac = AudioFileClip(output_audio)
                audio_duration = ac.duration
                ac.close()
            except Exception:
                audio_duration = len(raw_text.split()) * 0.35
            
            words = raw_text.split()
            avg_word_dur = audio_duration / max(1, len(words))
            for i, word in enumerate(words):
                ws = i * avg_word_dur
                subtitles.append({
                    "word": word,
                    "start": round(ws, 3),
                    "end": round(ws + avg_word_dur, 3),
                    "duration": round(max(0.1, avg_word_dur), 3)
                })

        # Write word-level timestamps directly (no grouping by default)
        output_data = group_subtitles(subtitles) if group else subtitles
        with open(output_subs, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)
            
        return output_audio, output_subs

    import threading
    result = {"audio": None, "subs": None, "error": None}
    
    def run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            a, s = loop.run_until_complete(amain())
            result["audio"] = a
            result["subs"] = s
        except Exception as e:
            result["error"] = e
        finally:
            loop.close()
            
    t = threading.Thread(target=run_in_thread)
    t.start()
    t.join()
    
    if result["error"]:
        print(f"Error in generate_voice: {result['error']}")
        return None, None
        
    return result["audio"], result["subs"]

if __name__ == "__main__":
    text = "99% fail this tech challenge! ... 1. Python was named after a snake. 2. CPU stands for core processing unit. The real answer is... Wait! Did you spot the fake?"
    a, s = generate_voice(text)
    print(f"Voice: {a}, Subs: {s}")

