import os
import json
import asyncio
import base64
import websockets
import httpx
import wave
import io
from typing import AsyncGenerator

class ElevenLabsTTSService:
    def __init__(self):
        self.api_key = os.getenv("ELEVEN_LAB_KEY")
        self.voice_id = os.getenv("ELEVEN_LAB_SPEKER")

    async def stream_tts(
        self,
        text_stream: AsyncGenerator[str, None],
        language_code: str = "hi-IN",
        pace: float = 1.1,
        speech_sample_rate: int = 8000,
        pipeline_start_time: float = None,
    ) -> AsyncGenerator[bytes, None]:
        
        if not self.api_key or not self.voice_id:
            print("[ElevenLabs] API Key or Voice ID missing.")
            return

        t_start = pipeline_start_time or asyncio.get_event_loop().time()
        def get_ms(): return (asyncio.get_event_loop().time() - t_start) * 1000

        # output_format=pcm_16000 ensures it natively matches Sarvam's 16kHz raw PCM chunk format
        connect_url = f"wss://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream-input?model_id=eleven_multilingual_v2&output_format=pcm_16000&optimize_streaming_latency=3"
        headers = {"xi-api-key": self.api_key}
        audio_queue: asyncio.Queue = asyncio.Queue()
        send_task = None
        receive_task = None

        async def send_text():
            try:
                first_frag = True
                
                # Send BOS to prime the engine
                await ws.send(json.dumps({
                    "text": " ",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}
                }))
                
                async for text_fragment in text_stream:
                    if text_fragment:
                        if first_frag:
                            print(f"[TTS Internal] Request: First chunk sent to ElevenLabs = {get_ms():.1f}ms")
                            first_frag = False
                        await ws.send(json.dumps({
                            "text": text_fragment,
                            "try_trigger_generation": True
                        }))

                # Send EOS
                await ws.send(json.dumps({"text": ""}))
            except asyncio.CancelledError:
                raise
            except Exception as e:
                await audio_queue.put(("error", e))

        async def receive_audio():
            try:
                first_audio = True
                while True:
                    try:
                        raw_msg = await ws.recv()
                        msg = json.loads(raw_msg)
                        
                        audio_b64 = msg.get("audio", "")
                        if audio_b64:
                            if first_audio:
                                print(f"[TTS Internal] Response: First audio bytes received from ElevenLabs = {get_ms():.1f}ms")
                                first_audio = False
                            pcm_bytes = base64.b64decode(audio_b64)
                            await audio_queue.put(("audio", pcm_bytes))

                        if msg.get("isFinal"):
                            await audio_queue.put(("final", None))
                            return
                        if msg.get("error"):
                            await audio_queue.put(("error", RuntimeError(msg["error"])))
                            return

                    except websockets.exceptions.ConnectionClosed:
                        await audio_queue.put(("error", RuntimeError("ElevenLabs WebSocket closed")))
                        return
                    except json.JSONDecodeError:
                        pass
            except Exception as e:
                await audio_queue.put(("error", e))

        try:
            print(f"[ElevenLabs WS] Attempting connection to: {connect_url}")
            async with websockets.connect(connect_url, extra_headers=headers) as ws:
                print(f"[TTS Internal] WS Connected to ElevenLabs = {get_ms():.1f}ms")
                
                send_task = asyncio.create_task(send_text())
                receive_task = asyncio.create_task(receive_audio())

                while True:
                    message_type, payload = await audio_queue.get()
                    if message_type == "audio":
                        yield payload
                    elif message_type == "final":
                        await send_task
                        break
                    else:
                        print(f"[ElevenLabs WS ERROR] {payload}")
                        raise payload
        except websockets.exceptions.WebSocketException as wse:
            print(f"[ElevenLabs WS Connection Error] {wse}")
            raise
        except Exception as ex:
            print(f"[ElevenLabs WS Exception] {ex}")
            raise
        except asyncio.CancelledError:
            raise
        finally:
            for task in (send_task, receive_task):
                if task and not task.done():
                    task.cancel()
            await asyncio.gather(
                *(task for task in (send_task, receive_task) if task),
                return_exceptions=True,
            )

    async def synthesize_realtime(self, text: str, speech_sample_rate: int = 8000, language_code: str = "hi-IN") -> str:
        if not self.api_key or not self.voice_id:
            return ""

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}?output_format=pcm_16000"
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.8
            }
        }
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=15.0)
            if response.status_code == 200:
                print(f"[ElevenLabs REST] Successfully generated greeting ({len(response.content)} bytes)")
                pcm_bytes = response.content
                wav_io = io.BytesIO()
                with wave.open(wav_io, 'wb') as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(16000)
                    wav.writeframes(pcm_bytes)
                return base64.b64encode(wav_io.getvalue()).decode('utf-8')
            else:
                print(f"[ElevenLabs REST Error] Status: {response.status_code}, Body: {response.text}")
                return ""
        except Exception as e:
            print(f"[ElevenLabs REST Exception] {e}")
            return ""
