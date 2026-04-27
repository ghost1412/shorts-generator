import asyncio
import edge_tts

async def debug_stream():
    text = "Hello world"
    voice = "en-US-AndrewNeural"
    communicate = edge_tts.Communicate(text, voice)
    async for chunk in communicate.stream():
        print(f"Type: {chunk['type']}")
        if chunk['type'] == 'WordBoundary':
             print(f"Found boundary: {chunk.get('text', 'N/A')}")

if __name__ == "__main__":
    asyncio.run(debug_stream())
