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
    """Groups word-by-word subtitles into cleaner, punctuation-aware chunks."""
    if not subtitles: return []
    grouped = []
    current = []

    for w in subtitles:
        current.append(w)
        # Group by punctuation or 4-word max limit
        word_text = w["word"].strip()
        if any(p in word_text for p in [".", "!", "?"]) or len(current) >= 4:
            grouped.append({
                "word": " ".join([x["word"] for x in current]),
                "start": current[0]["start"],
                "duration": sum(x["duration"] for x in current)
            })
            current = []

    if current:
        grouped.append({
            "word": " ".join([x["word"] for x in current]),
            "start": current[0]["start"],
            "duration": sum(x["duration"] for x in current)
        })

    return grouped

def generate_voice(text, output_audio="assets/voice.mp3", output_subs="assets/subs.json", voice_name="en-US-AvaNeural", rate="+15%", add_cta=True):
    """
    Generates voice with cinematic pacing and optimized subtitles.
    Relying on punctuation for stability instead of risky SSML.
    """
    raw_text = clean_for_tts(text)
    
    # 🟢 UPGRADE: Punctuation-based Pacing (Safe for all edge-tts versions)
    hook, rest = split_hook(raw_text)
    processed_rest = add_dramatic_pauses(rest or "")
    
    # Simple plain-text delivery with strategic pauses
    final_text = f"{hook} ... {processed_rest}"
    if add_cta:
        final_text += " ... Comment your answer now."

    os.makedirs(os.path.dirname(output_audio), exist_ok=True)
    
    async def amain():
        communicate = edge_tts.Communicate(final_text, voice_name, rate=rate)
        subtitles = []
        
        with open(output_audio, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] in ["WordBoundary", "word_boundary"]:
                    subtitles.append({
                        "word": chunk["text"],
                        "start": chunk["offset"] / 10_000_000,
                        "duration": max(0.05, chunk["duration"] / 10_000_000)
                    })
                elif chunk["type"] == "SentenceBoundary":
                    # 🟢 UPGRADE: Handle SentenceBoundary as a high-quality fallback for words
                    text = chunk["text"]
                    words = text.split()
                    if not words: continue
                    
                    sent_start = chunk["offset"] / 10_000_000
                    sent_dur = chunk["duration"] / 10_000_000
                    avg_word_dur = sent_dur / len(words)
                    
                    for i, word in enumerate(words):
                        subtitles.append({
                            "word": word,
                            "start": sent_start + (i * avg_word_dur),
                            "duration": max(0.1, avg_word_dur)
                        })

        # Final Fallback for words if everything else fails
        if not subtitles:
            audio_duration = 0
            try:
                # Robust import for both MoviePy 1.x and 2.x
                try:
                    from moviepy.audio.io.AudioFileClip import AudioFileClip
                except ImportError:
                    from moviepy.editor import AudioFileClip
                
                ac = AudioFileClip(output_audio)
                audio_duration = ac.duration
                ac.close()
            except Exception:
                # Better estimation: words * average speaking time
                audio_duration = len(raw_text.split()) * 0.35
            
            words = raw_text.split()
            avg_word_dur = audio_duration / max(1, len(words))
            for i, word in enumerate(words):
                subtitles.append({
                    "word": word,
                    "start": i * avg_word_dur,
                    "duration": max(0.1, avg_word_dur)
                })

        # Chunk subtitles for a premium UX
        grouped = group_subtitles(subtitles)
        with open(output_subs, "w", encoding="utf-8") as f:
            json.dump(grouped, f, indent=2)
            
        return output_audio, output_subs

    # Secure async execution for edge-tts
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
