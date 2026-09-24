import os
import json
import asyncio
import base64
import websockets
from typing import AsyncGenerator
#sk_l9c71ean_JtEakgoFNxPa5al1ndB4RDV2

class SarvamTTSService:
    # Sarvam's documented streaming configuration example uses a 50-character
    # processing threshold and 200-character maximum server-side phrase split.
    # This keeps conversational Hindi responsive while leaving segmentation to
    # Sarvam rather than introducing client-side prosody resets.
    MIN_BUFFER_SIZE = 50
    MAX_CHUNK_LENGTH = 200

    def __init__(self):
        self.api_key = os.getenv("SARVAM_API_KEY")
        self.ws_url = "wss://api.sarvam.ai/text-to-speech/ws"
        self.model = "bulbul:v3"

    async def stream_tts(
        self,
        text_stream: AsyncGenerator[str, None],
        language_code: str = "hi-IN",
        pace: float = 1.1,
        speech_sample_rate: int = 8000,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream one conversational turn through one Sarvam WebSocket.
        Sarvam owns buffering and phrase/sentence splitting for this turn.
        """
        if not self.api_key:
            print("[Sarvam TTS WS] SARVAM_API_KEY not configured")
            return

        connect_url = f"{self.ws_url}?model={self.model}&send_completion_event=true"
        headers = {"api-subscription-key": self.api_key}
        audio_queue: asyncio.Queue = asyncio.Queue()
        send_task = None
        receive_task = None

        async def send_text():
            try:
                fragment_count = 0
                async for text_fragment in text_stream:
                    if text_fragment:
                        # Raw protocol equivalent of AsyncSarvamAI.ws.convert().
                        # Preserve Gemini's fragments; Sarvam buffers/splits them.
                        await ws.send(json.dumps({
                            "type": "text",
                            "data": {"text": text_fragment}
                        }))
                        fragment_count += 1
                        print(
                            f"[Sarvam TTS WS] Gemini fragment sent via convert "
                            f"({fragment_count}): {text_fragment[:80]!r}"
                        )

                print("[Sarvam TTS WS] Gemini generation completed")
                await ws.send(json.dumps({"type": "flush"}))
                print("[Sarvam TTS WS] Flush sent")
            except asyncio.CancelledError:
                print("[Sarvam TTS WS] Text sender cancelled during barge-in cleanup")
                raise
            except Exception as e:
                print(f"[Sarvam TTS WS] Send error: {e}")
                await audio_queue.put(("error", e))

        async def receive_audio():
            try:
                while True:
                    try:
                        raw_msg = await ws.recv()
                        msg = json.loads(raw_msg)
                        msg_type = msg.get("type", "")

                        if msg_type == "audio":
                            audio_b64 = msg.get("data", {}).get("audio", "")
                            if audio_b64:
                                pcm_bytes = base64.b64decode(audio_b64)
                                print(f"[Sarvam TTS WS] Audio chunk received: {len(pcm_bytes)} bytes")
                                await audio_queue.put(("audio", pcm_bytes))

                        elif msg_type == "event":
                            event_type = msg.get("data", {}).get("event_type", "")
                            if event_type == "final":
                                print("[Sarvam TTS WS] Final completion event received")
                                await audio_queue.put(("final", None))
                                return

                        elif msg_type == "error":
                            err = msg.get("data", {}).get("message", "Unknown error")
                            print(f"[Sarvam TTS WS] Error: {err}")
                            await audio_queue.put(("error", RuntimeError(err)))
                            return

                    except websockets.exceptions.ConnectionClosed:
                        print("[Sarvam TTS WS] Connection closed during receive loop.")
                        await audio_queue.put(("error", RuntimeError("Sarvam WebSocket closed before final event")))
                        return
                    except json.JSONDecodeError:
                        print("[Sarvam TTS WS] Ignoring malformed server message")
            except Exception as e:
                print(f"[Sarvam TTS WS] Receive error: {e}")
                await audio_queue.put(("error", e))

        try:
            async with websockets.connect(connect_url, extra_headers=headers) as ws:
                print(f"[Sarvam TTS WS] Connected for turn at {speech_sample_rate}Hz")
                await ws.send(json.dumps({
                    "type": "config",
                    "data": {
                        "language_code": language_code,
                        "speaker": os.getenv("SARVAM_SPEAKER"),
                        "pace": pace,
                        "speech_sample_rate": speech_sample_rate,
                        "output_audio_codec": "linear16",
                        "min_buffer_size": self.MIN_BUFFER_SIZE,
                        "max_chunk_length": self.MAX_CHUNK_LENGTH,
                    }
                }))
                print(
                    "[Sarvam TTS WS] Config sent "
                    f"(min_buffer_size={self.MIN_BUFFER_SIZE}, "
                    f"max_chunk_length={self.MAX_CHUNK_LENGTH})"
                )

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
                        raise payload
        except asyncio.CancelledError:
            print("[Sarvam TTS WS] Turn cancelled; closing socket for barge-in cleanup")
            raise
        finally:
            for task in (send_task, receive_task):
                if task and not task.done():
                    task.cancel()
            await asyncio.gather(
                *(task for task in (send_task, receive_task) if task),
                return_exceptions=True,
            )
            print("[Sarvam TTS WS] WebSocket closed for turn")

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
