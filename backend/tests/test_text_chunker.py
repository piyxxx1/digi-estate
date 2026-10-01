import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.speech.text_chunker import chunk_for_tts, clean_text

async def fake_stream(tokens, delays=None):
    if delays is None:
        delays = [0] * len(tokens)
    for t, d in zip(tokens, delays):
        if d > 0:
            await asyncio.sleep(d)
        yield t

async def test_hindi_danda_split():
    text = "नमस्ते। यह एक टेस्ट है॥"
    tokens = list(text)
    chunks = []
    async for c in chunk_for_tts(fake_stream(tokens), first_min_chars=5, min_chars=5, max_chars=50):
        chunks.append(c)
    assert chunks == ["नमस्ते।", "यह एक टेस्ट है॥"], f"Got: {chunks}"

async def test_mixed_text():
    text = "मैं आपके लिए site visit book कर देता हूँ। आपका पूरा नाम क्या है?"
    tokens = list(text) # Yield character by character to trigger eager first-chunk flush
    chunks = []
    async for c in chunk_for_tts(fake_stream(tokens), first_min_chars=10, min_chars=10, max_chars=100):
        chunks.append(c)
    assert chunks == ["मैं आपके लिए site visit book कर देता हूँ।", "आपका पूरा नाम क्या है?"], f"Got: {chunks}"

async def test_decimals_and_abbreviations():
    text = "Dr. Smith bought 3.5 acres for Rs. 1,20,000 at 10:30 a.m. today!"
    chunks = []
    async for c in chunk_for_tts(fake_stream([text]), first_min_chars=10, min_chars=10, max_chars=100):
        chunks.append(c)
    assert chunks == ["Dr. Smith bought 3.5 acres for Rs. 1,20,000 at 10:30 a.m. today!"], f"Got: {chunks}"

async def test_max_chars_fallback():
    text = "a " * 100 # 200 chars, no punctuation
    chunks = []
    async for c in chunk_for_tts(fake_stream([text]), first_min_chars=10, min_chars=10, max_chars=50):
        chunks.append(c)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 50
    assert "".join(chunks).replace(" ", "") == text.replace(" ", "")

async def test_idle_flush():
    tokens = ["Hello ", "world, ", "how ", "are you?"]
    delays = [0, 0, 0.5, 0] # stall after "how " for 500ms
    chunks = []
    async for c in chunk_for_tts(fake_stream(tokens, delays), first_min_chars=50, min_chars=50, max_chars=100, idle_flush_ms=100):
        chunks.append(c)
    assert chunks[0] == "Hello world,", f"Got: {chunks}"
    assert chunks[1] == "how are you?", f"Got: {chunks}"

async def test_cancellation():
    async def infinite_stream():
        while True:
            yield "token "
            await asyncio.sleep(0.1)
            
    stream = infinite_stream()
    chunker = chunk_for_tts(stream, max_chars=20)
    
    chunks = []
    try:
        async for c in chunker:
            chunks.append(c)
            if len(chunks) == 2:
                raise asyncio.CancelledError()
    except asyncio.CancelledError:
        pass
    assert len(chunks) == 2

if __name__ == '__main__':
    asyncio.run(test_hindi_danda_split())
    asyncio.run(test_mixed_text())
    asyncio.run(test_decimals_and_abbreviations())
    asyncio.run(test_max_chars_fallback())
    asyncio.run(test_idle_flush())
    asyncio.run(test_cancellation())
    print("All tests passed!")
