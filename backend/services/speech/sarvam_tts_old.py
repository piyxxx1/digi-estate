import os
import json
import asyncio
import base64
import websockets
from typing import AsyncGenerator
#sk_l9c71ean_JtEakgoFNxPa5al1ndB4RDV2

class SarvamTTSService:
    def __init__(self):
        self.api_key = os.getenv("SARVAM_API_KEY")
        self.ws_url = "wss://api.sarvam.ai/text-to-speech/ws"
        self.model = "bulbul:v3"
        self.ws = None  # Persistent WebSocket session

    async def connect(self, speech_sample_rate: int = 8000, pace: float = 1.1, language_code: str = "hi-IN"):
        """Establish a persistent WebSocket connection for the duration of the call."""
        if self.ws:
            return  # Already connected
        
        if not self.api_key:
            print("[Sarvam TTS WS] SARVAM_API_KEY not configured")
            return

        connect_url = f"{self.ws_url}?model={self.model}&send_completion_event=true"
        headers = {"api-subscription-key": self.api_key}
        
        try:
            self.ws = await websockets.connect(connect_url, extra_headers=headers)
            print(f"[Sarvam TTS WS] Persistent connection established. Target rate: {speech_sample_rate}Hz")
            
            # Send dynamic sample rate in config
            config_msg = {
                "type": "config",
                "data": {
                    "language_code": language_code,
                    "speaker": os.getenv("SARVAM_SPEAKER"),
                    "pace": pace,
                    "speech_sample_rate": speech_sample_rate,
                    "output_audio_codec": "linear16",
                }
            }
            await self.ws.send(json.dumps(config_msg))
            print(f"[Sarvam TTS WS] Persistent Config sent ({speech_sample_rate}Hz)")
        except Exception as e:
            print(f"[Sarvam TTS WS] Failed to establish persistent connection: {e}")
            self.ws = None

    async def disconnect(self):
        """Close the persistent WebSocket connection at call end."""
        if self.ws:
            try:
                await self.ws.close()
                print("[Sarvam TTS WS] Persistent connection closed cleanly.")
            except Exception as e:
                print(f"[Sarvam TTS WS] Error closing persistent connection: {e}")
            finally:
                self.ws = None

    async def stream_tts(
        self,
        text_stream: AsyncGenerator[str, None],
        language_code: str = "hi-IN",
        pace: float = 1.1,
        speech_sample_rate: int = 8000,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream text chunks and receive synthesized audio using the persistent connection.
        If persistent connection is missing, dynamically connects.
        """
        if not self.ws:
            await self.connect(speech_sample_rate, pace, language_code)
            
        if not self.ws:
            print("[Sarvam TTS WS] Persistent connection unavailable, cannot stream.")
            return

        ws = self.ws
        audio_queue: asyncio.Queue = asyncio.Queue()
        done_event = asyncio.Event()

        async def send_text():
            try:
                chunk_count = 0
                async for text_chunk in text_stream:
                    if text_chunk and text_chunk.strip():
                        processed_chunk = text_chunk
                        # If language is Hindi/non-English and text contains no Devanagari (Hindi) script characters,
                        # append a silent Devanagari full stop (।) to avoid 400 validation error.
                        if not language_code.startswith("en") and not any(0x0900 <= ord(c) <= 0x097F for c in text_chunk):
                            processed_chunk = text_chunk + " ।"

                        await ws.send(json.dumps({
                            "type": "text",
                            "data": {"text": processed_chunk}
                        }))
                        chunk_count += 1
                        print(f"[Sarvam TTS WS] Text sent ({chunk_count}): '{processed_chunk[:50]}'")

                await ws.send(json.dumps({"type": "flush"}))
                print("[Sarvam TTS WS] Flush sent")

            except asyncio.CancelledError:
                print("[Sarvam TTS WS] Text sender cancelled")
                raise
            except Exception as e:
                print(f"[Sarvam TTS WS] Send error: {e}")

        async def receive_audio():
            try:
                while not done_event.is_set():
                    try:
                        raw_msg = await ws.recv()
                        msg = json.loads(raw_msg)
                        msg_type = msg.get("type", "")

                        if msg_type == "audio":
                            audio_b64 = msg.get("data", {}).get("audio", "")
                            if audio_b64:
                                pcm_bytes = base64.b64decode(audio_b64)
                                await audio_queue.put(pcm_bytes)

                        elif msg_type == "event":
                            event_type = msg.get("data", {}).get("event_type", "")
                            if event_type == "final":
                                break

                        elif msg_type == "error":
                            err = msg.get("data", {}).get("message", "Unknown error")
                            print(f"[Sarvam TTS WS] Error: {err}")
                            break

                    except websockets.exceptions.ConnectionClosed:
                        print("[Sarvam TTS WS] Connection closed during receive loop.")
                        break
                    except json.JSONDecodeError:
                        pass
            except Exception as e:
                print(f"[Sarvam TTS WS] Receive error: {e}")
            finally:
                await audio_queue.put(None)
                done_event.set()

        try:
            send_task = asyncio.create_task(send_text())
            recv_task = asyncio.create_task(receive_audio())

            while True:
                chunk = await audio_queue.get()
                if chunk is None:
                    break
                yield chunk

            await send_task
            await done_event.wait()
            
        except asyncio.CancelledError:
            print("[Sarvam TTS WS] Stream cancelled. Closing socket to prevent stale state...")
            send_task.cancel()
            recv_task.cancel()
            
            if self.ws:
                try:
                    await self.ws.close()
                except Exception:
                    pass
                self.ws = None
            raise

    # Kept for dynamic resampled greeting cache only
    async def synthesize_realtime(self, text: str, speech_sample_rate: int = 8000, language_code: str = "hi-IN") -> str:
        import httpx
        if not self.api_key:
            return ""

        payload = {
            "model": self.model,
            "inputs": [text],
            "speaker": os.getenv("SARVAM_SPEAKER"),
            "target_language_code": language_code,
            "output_audio_codec": "wav",
            "pace": 1.1,
            "speech_sample_rate": speech_sample_rate
        }
        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.sarvam.ai/text-to-speech",
                    json=payload,
                    headers=headers,
                    timeout=15.0
                )
            if response.status_code == 200:
                data = response.json()
                audios = data.get("audios", [])
                if audios:
                    return audios[0]
            else:
                print(f"[Sarvam TTS HTTP] API Error {response.status_code}: {response.text}")
            return ""
        except Exception as e:
            print(f"[Sarvam TTS HTTP] Exception: {e}")
            return ""
