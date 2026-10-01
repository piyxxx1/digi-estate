import os
import json
import asyncio
import base64
import websockets
from typing import AsyncGenerator

class SarvamSTTService:
    def __init__(self):
        self.api_key = os.getenv("SARVAM_API_KEY")
        # UPDATED: Use the new Realtime Streaming endpoint
        self.ws_url = "wss://api.sarvam.ai/speech-to-text-realtime/ws"
        # UPDATED: Use the v4 realtime model
        self.model = "saaras:v4"

    async def stream_transcription(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language_code: str = "hi-IN",
    ) -> AsyncGenerator[dict, None]:
        if not self.api_key:
            yield {"error": "SARVAM_API_KEY not configured"}
            return

        # UPDATED: Configured silence_duration_ms=400 to drop latency
        connect_url = (
            f"{self.ws_url}"
            f"?model={self.model}"
            f"&language_code={language_code}"
            f"&encoding=linear16"
            f"&sample_rate=16000"
            f"&endpointing=vad"
            f"&silence_duration_ms=400"
        )
        headers = {"api-subscription-key": self.api_key}

        try:
            async with websockets.connect(connect_url, extra_headers=headers) as ws:
                print("[Sarvam STT Realtime] Connected OK")

                async def send_audio():
                    """Stream audio chunks to STT WS."""
                    try:
                        async for chunk in audio_stream:
                            if isinstance(chunk, str):
                                pcm = base64.b64decode(chunk)
                            else:
                                pcm = chunk

                            # UPDATED: New audio input format for Realtime API
                            await ws.send(json.dumps({
                                "event": "audio_input",
                                "audio": base64.b64encode(pcm).decode("utf-8")
                            }))

                        # UPDATED: New flush format
                        await ws.send(json.dumps({"event": "flush"}))
                        print("[Sarvam STT Realtime] Flush sent")

                    except asyncio.CancelledError:
                        print("[Sarvam STT Realtime] Audio sender cancelled")
                    except Exception as e:
                        print(f"[Sarvam STT Realtime] Audio send error: {e}")

                send_task = asyncio.create_task(send_audio())

                async for raw_msg in ws:
                    try:
                        data = json.loads(raw_msg)
                        
                        # Realtime API uses 'event' instead of 'type'
                        event = data.get("event", "")
                        
                        # Handle new VAD events
                        if event == "vad.speech_start":
                            print("[Sarvam STT Realtime] VAD: speech_start")
                            yield {"type": "speech_start"}

                        elif event == "vad.speech_end":
                            print("[Sarvam STT Realtime] VAD: speech_end")
                            yield {"type": "speech_end"}

                        elif event == "transcript.final" or event == "transcript.partial":
                            print(f"[Sarvam STT Realtime] RAW TRANSCRIPT EVENT: {data}")
                            # The transcript text is provided under the 'text' key in Realtime API
                            transcript = data.get("text", "")
                            if not transcript and "transcript" in data:
                                transcript = data.get("transcript", "")
                                
                            if event == "transcript.final":
                                if transcript:
                                    print(f"[Sarvam STT Realtime] Final Transcript: {transcript}")
                                yield {"type": "data", "data": {"transcript": transcript}}
                            else:
                                # we could yield partials if we want to build UI later
                                pass

                        elif event == "error":
                            err_msg = data.get("message", "Unknown error")
                            print(f"[Sarvam STT Realtime] Error: {err_msg}")
                            yield {"error": err_msg}

                        else:
                            # Ignored messages like session.begin, config.updated, pong
                            print(f"[Sarvam STT Realtime] Unhandled event: {data}")
                            pass

                    except json.JSONDecodeError:
                        print(f"[Sarvam STT Realtime] Non-JSON: {raw_msg}")

                await send_task

        except websockets.exceptions.InvalidStatusCode as e:
            print(f"[Sarvam STT Realtime] Connection rejected: HTTP {e.status_code}")
            yield {"error": f"HTTP {e.status_code}"}
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"[Sarvam STT Realtime] Connection closed: {e}")
        except Exception as e:
            print(f"[Sarvam STT Realtime] WS Error: {type(e).__name__}: {e}")
            yield {"error": str(e)}
