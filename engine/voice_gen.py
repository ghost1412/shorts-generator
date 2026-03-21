import json
import os
import asyncio
import edge_tts
import re

def clean_for_tts(text):
    """
    Strips emojis, URLs, and common web noise while preserving useful symbols.
    """
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
    """Injects SSML break tags based on punctuation and logic."""
    # pause after numbers (facts list)
    text = re.sub(r'(\d+[:\.])', r'\1 <break time="300ms"/>', text)
    # pause before punchlines
    text = re.sub(r'(The real answer is)', r'<break time="400ms"/> \1', text)
    # pause after each fact line
    text = re.sub(r'(\.\s)', r'\1 <break time="250ms"/> ', text)
    # micro-pauses for rhythm
    text = re.sub(r',', ', <break time="120ms"/>', text)
    # ellipsis stays strongest pause
    text = text.replace("...", " <break time='600ms'/> ")
    return text

def emphasize_keywords(text):
    """Injects SSML emphasis for viral keywords safely using regex."""
    keywords = ["lie", "fake", "real answer", "spot", "shocking", "secret"]
    for k in keywords:
        text = re.sub(
            fr"\b({k})\b",
            lambda m: f"<emphasis level='strong'>{m.group(1)}</emphasis>",
            text,
            flags=re.IGNORECASE
        )
    return text

def split_hook(text):
    """Robustly splits text into hook and rest, falling back to first sentence."""
    # Try splitting by ellipsis first
    if "..." in text:
        parts = text.split("...", 1)
        return parts[0], parts[1]

    # fallback: first sentence as hook
    sentences = re.split(r'[.!?]', text, maxsplit=1)
    if len(sentences) > 1:
        return sentences[0], sentences[1]

    return text, ""

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
    """
    raw_text = clean_for_tts(text)
    
    # Add final drop CTA if requested
    if add_cta:
        raw_text += "... Comment your answer now."
    
    hook, rest = split_hook(raw_text)
    
    # Process the 'rest' for pauses. We rely purely on punctuation for pacing
    # since edge-tts treats custom <speak> wrapper as literal text.
    processed_rest = rest or ""
    
    # Simple plain-text delivery string (letting edge-tts build its own SSML internally)
    final_text = f"{hook}... {processed_rest}"

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

        # Fallback for words

        if not subtitles:
            audio_duration = 0
            try:
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

    try:
        import nest_asyncio
        nest_asyncio.apply()
        
        # Optimize event loop for repeated calls
        if asyncio.get_event_loop().is_running():
            return asyncio.create_task(amain())
        else:
            return asyncio.run(amain())
    except Exception as e:
        print(f"Error in generate_voice: {e}")
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(amain())
        except Exception as e2:
            print(f"Critical error in generate_voice: {e2}")
            return None, None

if __name__ == "__main__":
    text = "99% fail this tech challenge! ... 1. Python was named after a snake. 2. CPU stands for core processing unit. The real answer is... Wait! Did you spot the fake?"
    a, s = generate_voice(text)
    print(f"Voice: {a}, Subs: {s}")
