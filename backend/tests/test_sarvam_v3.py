import asyncio
import websockets
import os
import json
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("SARVAM_API_KEY")

async def test_sarvam_ws():
    ws_base_url = "wss://api.sarvam.ai/speech-to-text/ws"
    language_code = "hi-IN"
    model = "saaras:v3"
    
    ws_url = (
        f"{ws_base_url}"
        f"?model={model}"
        f"&language-code={language_code}"
        f"&mode=transcribe"
        f"&sample_rate=8000"
        f"&input_audio_codec=pcm_s16le"
    )
    
    # Try both cases for header
    headers = {"api-subscription-key": key}
    
    print(f"Connecting to: {ws_url}")
    try:
        async with websockets.connect(ws_url, extra_headers=headers) as ws:
            print("Successfully connected!")
            # Send a dummy packet or just close
    except Exception as e:
        print(f"Connection failed: {e}")
        if hasattr(e, 'status_code'):
            print(f"Status Code: {e.status_code}")
        if hasattr(e, 'headers'):
            print(f"Headers: {dict(e.headers)}")

if __name__ == "__main__":
    asyncio.run(test_sarvam_ws())
