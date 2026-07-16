# test_sarvam.py
import asyncio
import websockets
import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("SARVAM_API_KEY")
print(f"Key loaded: {key[:8]}..." if key else "Error: No key found!")

# ─── TEST 1: REST API (Models List) ───────────────────────────────
print("\n--- TEST 1: REST API (Models) ---")
try:
    # Testing with models endpoint to verify key
    r = requests.get(
        "https://api.sarvam.ai/speech-to-text", # Keep trying STT but handle 405 if it's just a POST endpoint
        headers={"api-subscription-key": key},
        timeout=10
    )
    print(f"Status: {r.status_code} | Body: {r.text[:200]}")
except Exception as e:
    print(f"REST Error: {e}")

# ─── TEST 2: WebSocket with key in query param ───────────────────
print("\n--- TEST 2: WebSocket (query param) ---")
async def test_ws_query():
    url = f"wss://api.sarvam.ai/v1/realtime?api-subscription-key={key}"
    try:
        async with websockets.connect(url) as ws:
            print("Connected via query param!")
    except Exception as e:
        print(f"Exception Type: {type(e)}")
        print(f"Attributes: {dir(e)}")
        if hasattr(e, 'response'):
            print(f"Response Status: {e.response.status_code}")
            print(f"Response Headers: {dict(e.response.headers)}")

try:
    asyncio.run(test_ws_query())
except Exception as e:
    print(f"Loop Error: {e}")

# ─── TEST 3: WebSocket with key in header ────────────────────────
print("\n--- TEST 3: WebSocket (header) ---")
async def test_ws_header():
    url = "wss://api.sarvam.ai/v1/realtime"
    try:
        async with websockets.connect(
            url,
            extra_headers={"api-subscription-key": key}
        ) as ws:
            print("Connected via header!")
    except Exception as e:
        print(f"Exception Type: {type(e)}")
        print(f"Error Message: {e}")
        if hasattr(e, 'status_code'):
            print(f"Status Code: {e.status_code}")
        if hasattr(e, 'headers'):
            print(f"Headers: {dict(e.headers)}")

try:
    asyncio.run(test_ws_header())
except Exception as e:
    print(f"Loop Error: {e}")

# ─── TEST 4: WebSocket v2 endpoint ──────────────────────────────
print("\n--- TEST 4: WebSocket /v2/realtime ---")
async def test_ws_v2():
    url = f"wss://api.sarvam.ai/v2/realtime?api-subscription-key={key}"
    try:
        async with websockets.connect(url) as ws:
            print("Connected to v2!")
    except Exception as e:
        print(f"Exception Type: {type(e)}")
        print(f"Error Message: {e}")
        if hasattr(e, 'status_code'):
            print(f"Status Code: {e.status_code}")
        if hasattr(e, 'headers'):
            print(f"Headers: {dict(e.headers)}")

try:
    asyncio.run(test_ws_v2())
except Exception as e:
    print(f"Loop Error: {e}")

# ─── TEST 5: REST POST (actual STT) ──────────────────────────────
print("\n--- TEST 5: REST POST (actual STT) ---")
import wave, struct

# Create a tiny valid WAV file in memory
def create_dummy_wav():
    import io
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(struct.pack('<' + 'h'*160, *([0]*160)))
    return buf.getvalue()

try:
    r = requests.post(
        "https://api.sarvam.ai/speech-to-text",
        headers={"api-subscription-key": key},
        files={"file": ("test.wav", create_dummy_wav(), "audio/wav")},
        data={"model": "saarika:v2.5"}, # Using v2.5 as it's common for batch
        timeout=15
    )
    print(f"Status: {r.status_code} | Body: {r.text[:300]}")
except Exception as e:
    print(f"REST Error: {e}")
