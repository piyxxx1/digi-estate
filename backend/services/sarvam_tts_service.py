import os
import json
import asyncio
import base64
import websockets
from typing import AsyncGenerator
#sk_l9c71ean_JtEakgoFNxPa5al1ndB4RDV2

class SarvamTTSService:
    # We now perform intelligent client-side chunking in text_chunker.py.
    # We want Sarvam to instantly synthesize whatever chunk we yield, without 
    # trying to do its own internal re-buffering or re-fragmenting.
    MIN_BUFFER_SIZE = 30
    MAX_CHUNK_LENGTH = 200

    def __init__(self):
        self.api_key = os.getenv("SARVAM_API_KEY")
        self.ws_url = "wss://api.sarvam.ai/text-to-speech/ws"
        self.model = "bulbul:v3"

    async def stream_tts(
        self,
        text_stream: AsyncGenerator[str, None],
        language_code: str = "hi-IN",
        pace: float = 1.0,
        speech_sample_rate: int = 8000,
        pipeline_start_time: float = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream one conversational turn through one Sarvam WebSocket.
        Sarvam owns buffering and phrase/sentence splitting for this turn.
        """
        if not self.api_key:
            return

        t_start = pipeline_start_time or asyncio.get_event_loop().time()
        def get_ms(): return (asyncio.get_event_loop().time() - t_start) * 1000

        connect_url = f"{self.ws_url}?model={self.model}&send_completion_event=true"
        headers = {"api-subscription-key": self.api_key}
        audio_queue: asyncio.Queue = asyncio.Queue()
        send_task = None
        receive_task = None

        async def send_text():
            try:
                first_frag = True
                fragment_count = 0
                async for text_fragment in text_stream:
                    if text_fragment:
                        if first_frag:
                            print(f"[TTS Internal] Request: First chunk sent to Sarvam = {get_ms():.1f}ms")
                            first_frag = False
                        # Raw protocol equivalent of AsyncSarvamAI.ws.convert().
                        # Preserve Gemini's fragments; Sarvam buffers/splits them.
                        await ws.send(json.dumps({
                            "type": "text",
                            "data": {"text": text_fragment}
                        }))
                        fragment_count += 1

                await ws.send(json.dumps({"type": "flush"}))
            except asyncio.CancelledError:
                raise
            except Exception as e:
                import traceback
                print(f"[Sarvam TTS Task ERROR] {e}")
                traceback.print_exc()
                await audio_queue.put(("error", e))

        async def receive_audio():
            try:
                first_audio = True
                while True:
                    try:
                        raw_msg = await ws.recv()
                        msg = json.loads(raw_msg)
                        msg_type = msg.get("type", "")

                        if msg_type == "audio":
                            audio_b64 = msg.get("data", {}).get("audio", "")
                            if audio_b64:
                                if first_audio:
                                    print(f"[TTS Internal] Response: First audio bytes received from Sarvam = {get_ms():.1f}ms")
                                    first_audio = False
                                pcm_bytes = base64.b64decode(audio_b64)
                                await audio_queue.put(("audio", pcm_bytes))

                        elif msg_type == "event":
                            event_type = msg.get("data", {}).get("event_type", "")
                            if event_type == "final":
                                await audio_queue.put(("final", None))
                                return

                        elif msg_type == "error":
                            err = msg.get("data", {}).get("message", "Unknown error")
                            await audio_queue.put(("error", RuntimeError(err)))
                            return

                    except websockets.exceptions.ConnectionClosed:
                        await audio_queue.put(("error", RuntimeError("Sarvam WebSocket closed before final event")))
                        return
                    except json.JSONDecodeError:
                        pass
            except Exception as e:
                import traceback
                print(f"[Sarvam TTS Task ERROR] {e}")
                traceback.print_exc()
                await audio_queue.put(("error", e))

        try:
            async with websockets.connect(connect_url, extra_headers=headers) as ws:
                print(f"[TTS Internal] WS Connected to Sarvam = {get_ms():.1f}ms")
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
            raise
        finally:
            for task in (send_task, receive_task):
                if task and not task.done():
                    task.cancel()
            await asyncio.gather(
                *(task for task in (send_task, receive_task) if task),
                return_exceptions=True,
            )

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
            "pace": 1.0,
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
            return ""
        except Exception as e:
            return ""
