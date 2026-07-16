import sys
import builtins

_original_print = builtins.print

def safe_print(*args, **kwargs):
    file = kwargs.get('file', sys.stdout)
    encoding = getattr(file, 'encoding', None) or 'utf-8'
    new_args = []
    for arg in args:
        if isinstance(arg, str):
            new_args.append(arg.encode(encoding, errors='replace').decode(encoding))
        else:
            new_args.append(arg)
    _original_print(*new_args, **kwargs)

builtins.print = safe_print

import os
import asyncio
import time
from dotenv import load_dotenv

load_dotenv()

# Add backend directory to sys.path
sys.path.append(os.path.abspath('.'))

from services.ai.ai_service import GeminiService
from services.speech.sarvam_tts_service import SarvamTTSService

async def test_pipeline():
    print("Initializing services...")
    ai_service = GeminiService()
    tts_service = SarvamTTSService()
    
    print("Connecting to Sarvam TTS WS...")
    start_conn = time.perf_counter()
    await tts_service.connect(speech_sample_rate=8000)
    print(f"Connected to Sarvam TTS in {(time.perf_counter() - start_conn)*1000:.2f}ms")
    
    user_message = "bhai plots kitne ka hai?"
    print(f"\nRunning pipeline for user message: '{user_message}'")
    
    pipeline_start = time.perf_counter()
    first_token_time = None
    first_audio_time = None
    
    # 1. Start Gemini streaming
    print("Starting Gemini Stream...")
    full_text = ""
    
    async def gemini_stream():
        nonlocal first_token_time, full_text
        async for chunk in ai_service.generate_response_stream(user_message, []):
            if first_token_time is None:
                first_token_time = time.perf_counter()
                print(f"TTFT (Gemini first token): {(first_token_time - pipeline_start)*1000:.2f}ms")
            full_text += chunk
            yield chunk

    # 2. Pipe into Sarvam TTS
    print("Piping Gemini stream into Sarvam TTS...")
    audio_chunks_count = 0
    try:
        async for audio_chunk in tts_service.stream_tts(gemini_stream(), speech_sample_rate=8000):
            if first_audio_time is None:
                first_audio_time = time.perf_counter()
                print(f"TTFA (First TTS audio chunk): {(first_audio_time - pipeline_start)*1000:.2f}ms")
            audio_chunks_count += 1
            
        print(f"\nPipeline finished.")
        print(f"Total Text: {full_text}")
        print(f"Total audio chunks received: {audio_chunks_count}")
        print(f"Total turn duration: {(time.perf_counter() - pipeline_start)*1000:.2f}ms")
    except Exception as e:
        print(f"Pipeline Error: {e}")
    finally:
        await tts_service.disconnect()

if __name__ == "__main__":
    asyncio.run(test_pipeline())
