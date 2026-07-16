import base64
import wave
import io
import audioop
from services.speech.audio_processor import AudioProcessor
from services.speech.sarvam_tts_service import SarvamTTSService
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test_conversion():
    tts = SarvamTTSService()
    ap = AudioProcessor()
    
    text = "Namaste!"
    print(f"Synthesizing: {text}")
    audio_b64 = await tts.synthesize_realtime(text)
    
    if not audio_b64:
        print("Failed to get audio from Sarvam")
        return
        
    print(f"Got audio, length: {len(audio_b64)}")
    
    try:
        exotel_audio = ap.wav_to_exotel_l16(audio_b64)
        print(f"Converted to Exotel format, length: {len(exotel_audio)}")
        
        # Verify it's valid PCM
        pcm_data = base64.b64decode(exotel_audio)
        print(f"PCM bytes length: {len(pcm_data)}")
        # At 8kHz, 16-bit, mono, length should be even
        if len(pcm_data) % 2 == 0:
            print("PCM length is valid (even)")
        else:
            print("PCM length is INVALID (odd)")
            
    except Exception as e:
        print(f"Conversion failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_conversion())
