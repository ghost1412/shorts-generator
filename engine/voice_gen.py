import json
import os
import asyncio
import edge_tts

def strip_emojis(text):
    """
    Strips emojis from text to prevent TTS from reading them verbally.
    """
    result = []
    allowed_chars = set(".,!?;:()-'\" ")
    for c in text:
        if ord(c) < 127:
            if c.isalnum() or c.isspace() or c in allowed_chars:
                result.append(c)
    return "".join(result)

def generate_voice(text, output_audio="assets/voice.mp3", output_subs="assets/subs.json", voice_name="en-US-AriaNeural"):
    """
    Generates voice and precise word-level subtitles using edge-tts Python API.
    """
    # Clean text for TTS
    tts_text = strip_emojis(text)
    
    os.makedirs(os.path.dirname(output_audio), exist_ok=True)
    
    async def amain():
        voice = voice_name
        communicate = edge_tts.Communicate(tts_text, voice)
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

        with open(output_subs, "w") as f:
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
