import os
import json
import asyncio
import base64
import websockets
from typing import AsyncGenerator


class SarvamSTTService:
    def __init__(self):
        self.api_key = os.getenv("SARVAM_API_KEY")
        self.ws_url = "wss://api.sarvam.ai/speech-to-text/ws"
        self.model = "saaras:v3"

    async def stream_transcription(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language_code: str = "hi-IN",
    ) -> AsyncGenerator[dict, None]:
        """
        TRUE WebSocket streaming STT per Sarvam docs:
        - All config via query params (no init message needed)
        - Send audio as base64 JSON chunks
        - Receive transcripts + VAD signals in real-time
        - Send {"type": "flush"} at end

        Query params used:
          model=saaras:v3
          language-code=hi-IN
          mode=transcribe
          sample_rate=16000        ← audio we send is 16kHz (upsampled from Exotel 8kHz)
          input_audio_codec=pcm_s16le
          vad_signals=true         ← get speech_start / speech_end events
          flush_signal=true        ← enable manual flush control
          high_vad_sensitivity=true
        """
        if not self.api_key:
            yield {"error": "SARVAM_API_KEY not configured"}
            return

        connect_url = (
            f"{self.ws_url}"
            f"?model={self.model}"
            f"&language-code={language_code}"
            f"&mode=transcribe"
            f"&sample_rate=16000"
            f"&input_audio_codec=pcm_s16le"
            f"&vad_signals=true"
            f"&flush_signal=true"
            f"&high_vad_sensitivity=true"
        )
        headers = {"api-subscription-key": self.api_key}

        try:
            async with websockets.connect(connect_url, extra_headers=headers) as ws:
                print("[Sarvam STT] Connected OK")

                async def send_audio():
                    """Stream audio chunks to STT WS."""
                    try:
                        async for chunk in audio_stream:
                            # chunk = raw 16kHz PCM bytes (upsampled in AudioProcessor)
                            if isinstance(chunk, str):
                                pcm = base64.b64decode(chunk)
                            else:
                                pcm = chunk

                            # Per Sarvam docs: send JSON with base64 audio
                            await ws.send(json.dumps({
                                "audio": {
                                    "data": base64.b64encode(pcm).decode("utf-8"),
                                    "sample_rate": 16000,
                                    "encoding": "audio/wav"
                                }
                            }))

                        # Per Sarvam docs: correct flush signal format
                        await ws.send(json.dumps({"type": "flush"}))
                        print("[Sarvam STT] Flush sent")

                    except asyncio.CancelledError:
                        print("[Sarvam STT] Audio sender cancelled")
                    except Exception as e:
                        print(f"[Sarvam STT] Audio send error: {e}")

                send_task = asyncio.create_task(send_audio())

                # Receive and yield transcripts + VAD events
                async for raw_msg in ws:
                    try:
                        data = json.loads(raw_msg)
                        msg_type = data.get("type", "")
                        signal_type = (
                            data.get("data", {}).get("signal_type")
                            or data.get("signal_type", "")
                        )

                        # Sarvam legacy streaming VAD can arrive either as a
                        # direct speech_start/speech_end message or as an
                        # events envelope containing START_SPEECH/END_SPEECH.
                        if msg_type == "speech_start" or signal_type == "START_SPEECH":
                            print("[Sarvam STT] VAD: speech_start")
                            yield {"type": "speech_start"}

                        elif msg_type == "speech_end" or signal_type == "END_SPEECH":
                            print("[Sarvam STT] VAD: speech_end")
                            yield {"type": "speech_end"}

                        elif msg_type == "data":
                            # Transcript result per docs:
                            # {"type":"data","data":{"transcript":"...","language_code":"...","metrics":{...}}}
                            transcript = data.get("data", {}).get("transcript", "")
                            if transcript:
                                print(f"[Sarvam STT] Transcript: {transcript}")
                            yield data

                        elif msg_type == "error":
                            err_msg = data.get("data", {}).get("message", "Unknown error")
                            print(f"[Sarvam STT] Error: {err_msg}")
                            yield {"error": err_msg}

                        else:
                            # Unknown message type
                            yield data

                    except json.JSONDecodeError:
                        print(f"[Sarvam STT] Non-JSON: {raw_msg}")

                await send_task

        except websockets.exceptions.InvalidStatusCode as e:
            print(f"[Sarvam STT] Connection rejected: HTTP {e.status_code}")
            yield {"error": f"HTTP {e.status_code}"}
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"[Sarvam STT] Connection closed: {e}")
        except Exception as e:
            print(f"[Sarvam STT] WS Error: {type(e).__name__}: {e}")
            yield {"error": str(e)}
