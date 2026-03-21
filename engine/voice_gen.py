import json
import os
import asyncio
import edge_tts

import re

def strip_emojis(text):
    """
    Strips emojis, URLs, and common web noise from text.
    """
    # 1. Strip URLs (more aggressive)
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    # 2. Strip standalone domains/versions like example.com or v1.0
    text = re.sub(r'\b\S+\.com\S*|\b\S+\.net\S*|\bv\d+\.\d+\b', '', text)
    
    # 3. Clean up stray punctuation like empty parentheses and extra spaces
    text = re.sub(r'\(\s*\)', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    # 4. Strip non-ASCII and emojis
    result = []
    allowed_chars = set(".,!?;:()-'\" ")
    for c in text:
        if ord(c) < 127:
            if c.isalnum() or c.isspace() or c in allowed_chars:
                result.append(c)
    return "".join(result)

def generate_voice(text, output_audio="assets/voice.mp3", output_subs="assets/subs.json", voice_name="en-US-AvaNeural", rate="+10%"):
    """
    Generates voice and precise word-level subtitles using edge-tts Python API.
    Added 'rate' support for punchy social media flow.
    """
    # Clean text for TTS
    tts_text = strip_emojis(text)
    
    # Replace '...' with SSML breaks for dramatic effect
    content_with_breaks = tts_text.replace("...", " <break time='500ms'/> ")
    ssml_text = f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='{voice_name}'>{content_with_breaks}</voice></speak>"
    
    os.makedirs(os.path.dirname(output_audio), exist_ok=True)
    
    async def amain():
        # Use SSML for better control over pauses
        communicate = edge_tts.Communicate(ssml_text, voice_name, rate=rate)
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
                elif chunk["type"] in ["SentenceBoundary", "sentence_boundary"]:
                    if not subtitles or subtitles[-1]["word"] != chunk["text"]:
                        # If we aren't getting word boundaries, we can use these
                        # We'll actually handle this post-stream if word boundaries are missing
                        pass

        # VERY ROBUST FALLBACK: If we have NO word boundaries, we must split the text manually
        # and estimate timings based on the audio duration.
        if not subtitles:
            print("[Warning] No word boundaries found. Estimating word timings from text.")
            audio_duration = 0
            try:
                from moviepy import AudioFileClip
                ac = AudioFileClip(output_audio)
                audio_duration = ac.duration
                ac.close()
            except Exception as e:
                print(f"[Warning] MoviePy failed to get duration: {e}. Using char-count estimation.")
                audio_duration = len(text) * 0.08 # very rough estimate
            
            words = text.split()
            avg_word_dur = audio_duration / max(1, len(words))
            for i, word in enumerate(words):
                subtitles.append({
                    "word": word,
                    "start": i * avg_word_dur,
                    "duration": max(0.1, avg_word_dur)
                })

        with open(output_subs, "w", encoding="utf-8") as f:
            json.dump(subtitles, f, indent=2)
            
        return output_audio, output_subs

    try:
        # Modern way to run async code in sync context
        return asyncio.run(amain())
    except RuntimeError:
        # Fallback if an event loop is already running (e.g., in some REPLs or frameworks)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(amain())
    except Exception as e:
        print(f"Error in generate_voice: {e}")
        return None, None

if __name__ == "__main__":
    text = "Did you know? Octopuses have three hearts and blue blood."
    a, s = generate_voice(text)
    print(f"Voice: {a}, Subs: {s}")
