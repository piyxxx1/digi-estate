import json
import os
import base64
import asyncio
import datetime

def get_boundary_ts():
    return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from services.speech.sarvam_stt_service import SarvamSTTService
from services.speech.sarvam_tts_service import SarvamTTSService
from services.speech.audio_processor import AudioProcessor
from services.ai.ai_service import GeminiService
from services.ai.memory_manager import MemoryManager
from utils.call_logger import initialize_call_log, finalize_call_log
import wave
import math
import struct
import time
router = APIRouter()

DEBUG_AUDIO = os.getenv("DEBUG_AUDIO", "1") == "1"
DEBUG_AUDIO_DIR = os.getenv("DEBUG_AUDIO_DIR", "/tmp/call_audio")

def _write_wav(path: str, pcm: bytes, rate: int):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm)

async def save_wav(path: str, pcm, rate: int):
    if DEBUG_AUDIO and pcm:
        await asyncio.to_thread(_write_wav, path, bytes(pcm), rate)


@router.post("/status-callback")
async def exotel_status_callback(request: Request):
    """Webhook to receive call status updates from Exotel (e.g., busy, failed, completed)."""
    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid") or "Unknown"
        status = form_data.get("Status") or "Unknown"
        to_number = form_data.get("To") or "Unknown"
        from_number = form_data.get("From") or "Unknown"
        
        # Determine the external number (customer) vs Exophone
        # Exotel outbound API usually sets From = Customer, To = Exophone 
        # But just in case, we log both if one isn't clearly the Exophone.
        phone_number = from_number if from_number != "Unknown" else to_number
        
        
        # --- Channel Queue Manager Integration ---
        from services.telephony.channel_manager import ChannelManager
        from services.telephony.queue_dispatcher import QueueDispatcher

        channel_manager = ChannelManager()
        dispatcher = QueueDispatcher()

        # Try to release the channel if this CallSid matches
        released_channel_id = await channel_manager.release_channel_by_sid(call_sid)
        
        if released_channel_id:
            asyncio.create_task(dispatcher.dispatch())        # --- Finalize Call Log for Non-WS Call (Failed/Busy calls before WS starts) ---
        if status.lower() not in ["in-progress", "ringing"]:
            if call_sid not in active_exotel_websockets:
                asyncio.create_task(finalize_call_log(
                    call_sid=call_sid,
                    duration=0,
                    history_messages=[]
                ))

        return {"status": "success"}
    except Exception as e:
        return {"status": "error"}

# Global registry for active websockets so we can forcefully terminate them
active_exotel_websockets: dict[str, WebSocket] = {}
force_terminated_calls = set()

# Lazy cache mapped by sample_rate: {8000: [...], 16000: [...], 24000: [...]}
_greeting_chunks_cache: dict[int, list[str]] = {}
_greeting_cache_lock = asyncio.Lock()
import os
_gender = os.getenv("SPEAKER_GENDER", "male").lower()
_name = os.getenv("SPEAKER_NAME") or os.getenv("speaker_name")
if not _name:
    _sarvam_spk = os.getenv("SARVAM_SPEAKER")
    if _sarvam_spk:
        _name = _sarvam_spk.capitalize()
    else:
        _name = "रोहन" if _gender == "male" else "प्रिया"

if _gender == "female":
    _GREETING_TEXT = f"नमस्ते, मैं {_name} बोल रही हूँ, डिजी-एस्टेट से। आज मैं आपकी कैसे मदद कर सकती हूँ?"
    _SHORT_FILLERS_TEXT = [ "hmmmmm ok","अच्छा।", "ठीक है।", "जी।", "बिलकुल।", "ज़रूर।", "समझ गई।", "जी बिलकुल।", "ओके।"]
else:
    _GREETING_TEXT = f"नमस्ते, मैं {_name} बोल रहा हूँ, डिजी-एस्टेट से। आज मैं आपकी कैसे मदद कर सकता हूँ?"
    _SHORT_FILLERS_TEXT = [ "hmmmmm ok","अच्छा।", "ठीक है।", "जी।", "बिलकुल।", "ज़रूर।", "समझ गया।", "जी बिलकुल।", "ओके।"]

_short_fillers_cache: dict[int, list[bytes]] = {}
_short_fillers_lock = asyncio.Lock()

async def _ensure_short_fillers_cached(sample_rate: int):
    global _short_fillers_cache
    if sample_rate in _short_fillers_cache:
        return
    async with _short_fillers_lock:
        if sample_rate in _short_fillers_cache:
            return
        
        print(f"[Startup] Pre-caching short fillers at {sample_rate}Hz...")
        from services.speech.sarvam_tts_service import SarvamTTSService
        tts_service = SarvamTTSService()
        fillers_pcm = []
        
        for text in _SHORT_FILLERS_TEXT:
            async def _mock_stream(t=text):
                yield t
            audio_bytes = bytearray()
            try:
                # Need to use an async generator directly
                async for chunk in tts_service.stream_tts(_mock_stream(), language_code="hi-IN", pace=1.0, speech_sample_rate=sample_rate):
                    if isinstance(chunk, bytes):
                        audio_bytes.extend(chunk)
                if audio_bytes:
                    fillers_pcm.append(bytes(audio_bytes))
            except Exception as e:
                print(f"[Filler Cache Error] {e}")
        
        if fillers_pcm:
            _short_fillers_cache[sample_rate] = fillers_pcm
            print(f"[Startup] Cached {len(fillers_pcm)} short fillers at {sample_rate}Hz.")
        else:
            print(f"[Startup] ERROR: Failed to cache any short fillers at {sample_rate}Hz.")



async def _ensure_greeting_cached(sample_rate: int):
    """Generate greeting audio once per sample rate and cache it. Thread-safe."""
    global _greeting_chunks_cache
    if sample_rate in _greeting_chunks_cache:
        return  # Already cached for this rate

    async with _greeting_cache_lock:
        if sample_rate in _greeting_chunks_cache:  # Double-check
            return

        tts_service = SarvamTTSService()
        audio_processor = AudioProcessor()
        import audioop

        async def _mock_text_stream():
            yield _GREETING_TEXT
            
        audio_bytes_array = bytearray()
        try:
            async for pcm_chunk in tts_service.stream_tts(
                _mock_text_stream(),
                language_code="hi-IN",
                pace=1.0,
                speech_sample_rate=sample_rate
            ):
                audio_bytes_array.extend(pcm_chunk)
        except Exception as e:
            print(f"[Greeting Cache] Error generating greeting: {e}")
            
        audio_bytes = bytes(audio_bytes_array)
        if not audio_bytes:
            print("[Greeting Cache] Failed to generate audio for greeting.")
            return

        # Dynamic silence threshold based on sample rate
        # 320 bytes = 20ms @ 8kHz (16-bit)
        # For sample_rate: 20ms frame = sample_rate * 2 * 0.02
        frame_size_20ms = int(sample_rate * 2 * 0.02)

        while len(audio_bytes) > frame_size_20ms and audioop.rms(audio_bytes[:frame_size_20ms], 2) < 5:
            audio_bytes = audio_bytes[frame_size_20ms:]
        while len(audio_bytes) > frame_size_20ms and audioop.rms(audio_bytes[-frame_size_20ms:], 2) < 5:
            audio_bytes = audio_bytes[:-frame_size_20ms]

        # 40ms chunk sizes dynamically calculated per sample rate
        chunk_size = int(sample_rate * 2 * 0.04)  # 40ms
        chunks = []
        for i in range(0, len(audio_bytes), chunk_size):
            chunk_data = audio_bytes[i:i + chunk_size]
            if len(chunk_data) % frame_size_20ms != 0:
                pad = frame_size_20ms - (len(chunk_data) % frame_size_20ms)
                chunk_data = chunk_data + b'\x00' * pad
            chunks.append(base64.b64encode(chunk_data).decode('utf-8'))

        _greeting_chunks_cache[sample_rate] = chunks

# ── Dynamic Fast Path Pre-Caching ──
SCRIPTED_REPLIES = [
    "मैं आपके लिए site visit book कर देता हूँ। आपका पूरा नाम क्या है?",
    "Thank you! आपका contact number क्या है?",
    "आप किस date को visit करना चाहेंगे?",
    "तो मैं आपका visit confirm कर रहा हूँ। हमारी team एक दिन पहले details share करेगी। धन्यवाद!",
    "ठीक है, मैं आपको कब कॉल कर सकती हूँ?"
]
_fast_path_cache: dict[int, dict[str, list[str]]] = {}
_fast_path_lock = asyncio.Lock()

async def _ensure_fast_path_cached(text: str, sample_rate: int):
    """Pre-generate audio for scripted responses and cache them at dynamic sample rates."""
    global _fast_path_cache
    if sample_rate not in _fast_path_cache:
        _fast_path_cache[sample_rate] = {}
    if text in _fast_path_cache[sample_rate]:
        return

    async with _fast_path_lock:
        if text in _fast_path_cache[sample_rate]:  # Double-check
            return

        tts_service = SarvamTTSService()
        audio_processor = AudioProcessor()
        import audioop

        audio_b64_raw = await tts_service.synthesize_realtime(text, speech_sample_rate=sample_rate)
        if not audio_b64_raw:
            return

        # Resample and convert to raw PCM for this specific sample rate
        audio_b64_pcm = audio_processor.wav_to_exotel_pcm(audio_b64_raw, target_sample_rate=sample_rate)
        audio_bytes = base64.b64decode(audio_b64_pcm)

        frame_size_20ms = int(sample_rate * 2 * 0.02)
        while len(audio_bytes) > frame_size_20ms and audioop.rms(audio_bytes[:frame_size_20ms], 2) < 5:
            audio_bytes = audio_bytes[frame_size_20ms:]
        while len(audio_bytes) > frame_size_20ms and audioop.rms(audio_bytes[-frame_size_20ms:], 2) < 5:
            audio_bytes = audio_bytes[:-frame_size_20ms]

        chunk_size = int(sample_rate * 2 * 0.04)  # 40ms chunks
        chunks = []
        for i in range(0, len(audio_bytes), chunk_size):
            chunk_data = audio_bytes[i:i + chunk_size]
            if len(chunk_data) % frame_size_20ms != 0:
                pad = frame_size_20ms - (len(chunk_data) % frame_size_20ms)
                chunk_data = chunk_data + b'\x00' * pad
            chunks.append(base64.b64encode(chunk_data).decode('utf-8'))

        _fast_path_cache[sample_rate][text] = chunks


@router.post("/calls/{call_sid}/terminate")
async def terminate_call_ws(call_sid: str):
    """
    Forcefully terminates the Exotel WebSocket for the given call_sid,
    which triggers Exotel to hang up the call on the device.
    If the WS is not yet connected (call is still ringing), it marks it to be terminated
    immediately upon connection. It also attempts to cancel the call via Exotel REST API.
    """
    force_terminated_calls.add(call_sid)
    
    # Try to cancel the call on Exotel's end if it's still ringing
    try:
        from services.telephony.exotel_service import ExotelService
        import httpx
        exotel = ExotelService()
        url = f"{exotel.base_url}/Calls/{call_sid}.json"
        
        # Exotel doesn't have a standard DELETE /Kill for all V1 calls, but we can attempt to POST Status=completed or Status=canceled
        async with httpx.AsyncClient() as client:
            # We fire and forget this request just in case Exotel respects it
            await client.post(url, data={"Status": "canceled"})
            await client.post(url, data={"Status": "completed"})
    except Exception as api_err:
        pass
    
    ws = active_exotel_websockets.get(call_sid)
    if ws:
        try:
            await ws.close()
            active_exotel_websockets.pop(call_sid, None)
            return {"status": "success", "message": "Call terminated via WebSocket close."}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "success", "message": "Call marked for termination upon connection."}

@router.websocket("/exotel")
async def exotel_stream_handler(websocket: WebSocket):
    await websocket.accept()
    
    sent_audio = bytearray()
    caller_audio = bytearray()
    sent_end_time = None
    turn_counter = 0

    def record_sent(chunk_data: bytes):
        """Log a frame as it leaves for Exotel, padding silence for gaps so the file matches the call timeline."""
        nonlocal sent_end_time
        if not DEBUG_AUDIO:
            return
        now = asyncio.get_event_loop().time()
        if sent_end_time is None:
            sent_end_time = now
        if now > sent_end_time + 0.02:
            gap_bytes = int((now - sent_end_time) * sample_rate) * 2
            sent_audio.extend(b"\x00" * gap_bytes)
            sent_end_time = now
        sent_audio.extend(chunk_data)
        sent_end_time += len(chunk_data) / (sample_rate * 2)
    # ── Dynamic Sample Rate Extraction ──
    # Exotel passes `sample-rate=24000` or `sample_rate=24000` as query params. Default is 16000Hz if not specified.
    param_rate = websocket.query_params.get("sample-rate") or websocket.query_params.get("sample_rate") or "16000"
    try:
        sample_rate = int(param_rate)
    except ValueError:
        sample_rate = 16000

    # Start caching greeting eagerly on connect to reduce start latency
    asyncio.create_task(_ensure_greeting_cached(sample_rate))

    # Frame and Chunk parameters calculated dynamically
    frame_size_20ms = int(sample_rate * 2 * 0.02)  # Multiple check pad (20ms)
    chunk_size_40ms = int(sample_rate * 2 * 0.04)  # Playback chunk (40ms)

    stt_service = SarvamSTTService()
    tts_service = SarvamTTSService()
    audio_processor = AudioProcessor()
    ai_service = GeminiService()
    memory_manager = MemoryManager()
    
    stream_sid = None
    call_sid = None
    stream_pcm_next_time = 0

    async def send_paced(chunks_b64, generation: int):
        """Send a sequence of base64 PCM chunks to the websocket at real-time
        cadence using absolute scheduling (prevents drift accumulation)."""
        loop = asyncio.get_event_loop()
        next_time = loop.time()
        for chunk_b64 in chunks_b64:
            if is_closed or not playback_is_current(generation):
                break
            if not await wait_for_playback_slot(next_time, generation):
                break
            if not playback_is_current(generation):
                break
            chunk_bytes = base64.b64decode(chunk_b64)
            duration = len(chunk_bytes) / (sample_rate * 2)
            payload = json.dumps({
                "event": "media",
                "stream_sid": stream_sid,
                "media": {"payload": chunk_b64}
            }, separators=(',', ':'))
            await websocket.send_text(payload)
            next_time += duration

    call_start_time = None
    turn_metrics = {}

    def print_latency_block(metrics):
        try:
            if "speech_end" not in metrics or "exotel_first_audio_sent" not in metrics:
                return
            
            speech_dur = int((metrics.get("speech_end", 0) - metrics.get("speech_start", metrics.get("speech_end", 0))) * 1000)
            stt_fin = int((metrics.get("stt_final", metrics.get("speech_end", 0)) - metrics.get("speech_end", 0)) * 1000)
            
            gem_start_delay = int((metrics.get("gemini_start", metrics.get("stt_final", 0)) - metrics.get("stt_final", 0)) * 1000)
            gem_ttft = int((metrics.get("gemini_first_token", metrics.get("gemini_start", 0)) - metrics.get("gemini_start", 0)) * 1000)
            gem_total = int((metrics.get("gemini_complete", metrics.get("gemini_start", 0)) - metrics.get("gemini_start", 0)) * 1000)
            
            tts_start_delay = int((metrics.get("tts_start", metrics.get("gemini_first_token", 0)) - metrics.get("gemini_first_token", 0)) * 1000)
            tts_first_audio = int((metrics.get("tts_first_audio", metrics.get("tts_start", 0)) - metrics.get("tts_start", 0)) * 1000)
            
            exotel_delay = int((metrics.get("exotel_first_audio_sent", metrics.get("tts_first_audio", 0)) - metrics.get("tts_first_audio", 0)) * 1000)
            
            server_latency = int((metrics.get("exotel_first_audio_sent", 0) - metrics.get("speech_end", 0)) * 1000)
            
            print("\n========== TURN LATENCY ==========")
            print(f"Speech duration:       {speech_dur:5d} ms")
            print(f"STT finalization:      {stt_fin:5d} ms")
            print(f"Gemini start delay:    {gem_start_delay:5d} ms")
            print(f"Gemini TTFT:           {gem_ttft:5d} ms")
            print(f"Gemini total:          {gem_total:5d} ms")
            print(f"TTS start delay:       {tts_start_delay:5d} ms")
            print(f"TTS first audio:       {tts_first_audio:5d} ms")
            print(f"Exotel send delay:     {exotel_delay:5d} ms")
            print("-----------------------------------")
            print(f"Server response latency:{server_latency:5d} ms")
            print("===================================\n")
        except Exception as e:
            print(f"Error printing latency: {e}")

    audio_queue = asyncio.Queue()
    is_closed = False
    greeting_task = None
    greeting_playing = False
    response_task = None
    bot_speaking = False  # Flag: True when bot is actively playing audio
    
    # Debounce state
    latest_transcript = ""
    last_transcript_time = 0
    current_pipeline_audio_sent = False
    current_pipeline_text = ""
    speech_start_time = 0
    user_currently_speaking = False
    bot_finished_at = None
    silence_prompt_active = False
    sarvam_audio = bytearray()
    debug_exotel_logged_first_chunk = False

    def reset_post_bot_silence():
        """Cancel the post-playback silence window when the user is active."""
        nonlocal bot_finished_at, silence_prompt_active
        bot_finished_at = None
        silence_prompt_active = False

    async def audio_generator():
        while True:
            chunk = await audio_queue.get()
            if chunk is None:
                break
            yield chunk

    async def send_greeting():
        nonlocal stream_sid, is_closed, greeting_playing, bot_speaking
        
        if not stream_sid or is_closed:
            return

        playback_id, exotel_playback_done = begin_playback()
        try:
            # Dynamically ensure cached for target sample_rate
            await _ensure_greeting_cached(sample_rate)
            if not playback_is_current(playback_id):
                return
            chunks = _greeting_chunks_cache.get(sample_rate, [])
            
            exotel_playback_done_events[playback_id] = exotel_playback_done
            bot_speaking = True
            
            for chunk_b64 in chunks:
                if is_closed or not playback_is_current(playback_id):
                    break
                import base64
                await stream_pcm_to_exotel(base64.b64decode(chunk_b64), playback_id)
            await stream_pcm_to_exotel(b"", playback_id)
            await wait_for_exotel_playback_done(playback_id, exotel_playback_done)
            
            bot_speaking = False
            greeting_playing = False
            memory_manager.save_interaction(call_sid or "default_user", "assistant", _GREETING_TEXT)
        except asyncio.CancelledError:
            exotel_playback_done.set()
            bot_speaking = False
            greeting_playing = False
            memory_manager.save_interaction(call_sid or "default_user", "assistant", "नमस्ते, मैं Priya बोल रही हूँ, Charaktaal Eco Village से...")
            raise
        except Exception as e:
            import traceback
            print(f"[send_greeting ERROR] {e}")
            traceback.print_exc()
            exotel_playback_done.set()
            bot_speaking = False
            greeting_playing = False

    async def send_clear():
        """Send clear event to Exotel to flush its audio buffer on barge-in."""
        nonlocal stream_sid, is_closed, exotel_next_send_time
        if not stream_sid or is_closed:
            return
        try:
            payload = json.dumps({
                "event": "clear",
                "stream_sid": stream_sid
            }, separators=(',', ':'))
            await websocket.send_text(payload)
        except Exception as e:
            pass

    async def stop_bot_playback_for_barge_in():
        """Invalidate stale audio before asking Exotel to clear its buffer."""
        nonlocal greeting_playing, bot_speaking

        # Cancel producers first, then invalidate their generation before any
        # local/external buffer operation. The permanent sender task remains
        # alive and rejects every old-generation item.
        bot_speaking = False
        if greeting_playing and greeting_task and not greeting_task.done():
            greeting_task.cancel()
            greeting_playing = False
        if response_task and not response_task.done():
            response_task.cancel()

        invalidate_playback()
        await send_clear()

    async def handle_sarvam_responses():
        nonlocal stream_sid, latest_transcript, last_transcript_time, speech_start_time, response_task, greeting_task, greeting_playing, bot_speaking, user_currently_speaking
        try:
            async for result in stt_service.stream_transcription(audio_generator()):
                msg_type = result.get("type", "")

                # VAD: User STARTED speaking → stop bot playback immediately.
                # Do not wait for transcript recognition; it arrives too late for
                # natural barge-in behavior.
                if msg_type == "speech_start":
                    user_currently_speaking = True
                    speech_start_time = asyncio.get_event_loop().time()
                    turn_metrics.clear()
                    turn_metrics["speech_start"] = speech_start_time
                    reset_post_bot_silence()
                    
                    async def barge_in_check():
                        await asyncio.sleep(0.50)
                        if user_currently_speaking and (bot_speaking or greeting_playing or playback_may_be_active):
                            print(f"[{get_boundary_ts()}] [Boundary] Barge-in triggered after 500ms of speech")
                            await stop_bot_playback_for_barge_in()
                            
                    asyncio.create_task(barge_in_check())
                    continue

                # VAD: User STOPPED speaking → accelerate silence timer
                if msg_type == "speech_end":
                    print(f"[{get_boundary_ts()}] [Boundary] Caller speech_end")
                    user_currently_speaking = False
                    turn_metrics["speech_end"] = asyncio.get_event_loop().time()
                    last_transcript_time = asyncio.get_event_loop().time() - 0.2
                    reset_post_bot_silence()
                    continue

                # Transcript result
                transcript = ""
                if msg_type == "data":
                    transcript = result.get("data", {}).get("transcript", "")
                elif result.get("is_final") or msg_type == "transcript.final":
                    transcript = result.get("transcript", "")

                if transcript:
                    # Any recognized user audio ends the current post-bot idle
                    # period, even if the text is later filtered as a weak
                    # barge-in/echo candidate.
                    reset_post_bot_silence()
                    cleaned_t = transcript.strip().lower().replace(".", "").replace("?", "").replace("।", "")
                    ignore_list = ["हम्म", "क्या", "hmm", "han", "kya", "hello", "hi", "hey", "हाँ", "हा", "जी", "अच्छा", "हेलो"]

                    # VAD is the primary gate while the bot is speaking
                    if bot_speaking:
                        if not user_currently_speaking:
                            continue
                        if cleaned_t in ignore_list:
                            continue

                    # Robust Filter: Ignore inside ignore list for active barge-in
                    if cleaned_t not in ignore_list:
                        if latest_transcript:
                            latest_transcript += " " + transcript
                        else:
                            latest_transcript = transcript
                        if user_currently_speaking:
                            last_transcript_time = asyncio.get_event_loop().time()
                        reset_post_bot_silence()

                        # FIX 2: Perform barge-in cancellation + clear Exotel buffer
                        if ((greeting_playing and greeting_task and not greeting_task.done()) or
                                (response_task and not response_task.done())):
                            await stop_bot_playback_for_barge_in()
                    else:
                        # Accept it for standard processing only if AI is silent
                        if not greeting_playing and (response_task is None or response_task.done()):
                            if latest_transcript:
                                latest_transcript += " " + transcript
                            else:
                                latest_transcript = transcript
                            last_transcript_time = asyncio.get_event_loop().time()
                            reset_post_bot_silence()

                elif "error" in result:
                    print(f"[Sarvam Error] {result['error']}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            import traceback
            print(f"[handle_sarvam_responses ERROR] {e}")
            traceback.print_exc()
    async def send_mark(mark_name: str):
        """Send mark event to Exotel (Stream Applet — signals playback milestone)."""
        nonlocal stream_sid, is_closed
        if not stream_sid or is_closed:
            return
        try:
            payload = json.dumps({
                "event": "mark",
                "stream_sid": stream_sid,
                "mark": {"name": mark_name}
            }, separators=(',', ':'))
            await websocket.send_text(payload)
        except Exception as e:
            pass

    # Keep this buffer outside stream_pcm_to_exotel()
    exotel_pcm_queue = asyncio.Queue()
    exotel_pcm_buffer = bytearray()
    exotel_next_send_time = 0.0
    playback_generation = 0
    playback_may_be_active = False
    exotel_buffer_generation = 0
    playback_interrupt_event = asyncio.Event()
    # A response owns one initially-clear completion Event, keyed by its
    # generation so a cancelled playback cannot release a later response.
    exotel_playback_done_events = {}

    def playback_is_current(generation: int) -> bool:
        return generation == playback_generation and not playback_interrupt_event.is_set()

    def begin_playback() -> tuple[int, asyncio.Event]:
        nonlocal playback_generation, playback_may_be_active
        previous_exotel_playback_done = exotel_playback_done_events.pop(playback_generation, None)
        if previous_exotel_playback_done:
            # Starting a replacement generation must not strand a previous
            # pipeline that was waiting for its own completion event.
            previous_exotel_playback_done.set()
        playback_generation += 1
        playback_may_be_active = True
        playback_interrupt_event.clear()
        exotel_playback_done = asyncio.Event()
        exotel_playback_done_events[playback_generation] = exotel_playback_done
        return playback_generation, exotel_playback_done

    def finish_exotel_playback(generation: int):
        """Release the waiter for a sender-drained playback generation."""
        exotel_playback_done = exotel_playback_done_events.get(generation)
        if exotel_playback_done:
            exotel_playback_done.set()

    def invalidate_playback():
        nonlocal playback_generation, playback_may_be_active, exotel_next_send_time, exotel_buffer_generation
        previous_generation = playback_generation
        previous_exotel_playback_done = exotel_playback_done_events.pop(previous_generation, None)
        if previous_exotel_playback_done:
            # A barge-in must also unblock a pipeline already waiting for its
            # final PCM frame to leave the sender.
            previous_exotel_playback_done.set()
        playback_generation += 1
        playback_may_be_active = False
        playback_interrupt_event.set()
        exotel_pcm_buffer.clear()
        while not exotel_pcm_queue.empty():
            try:
                exotel_pcm_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        exotel_buffer_generation = playback_generation
        exotel_next_send_time = 0.0

    async def wait_for_playback_slot(target_time: float, generation: int) -> bool:
        delay = target_time - asyncio.get_event_loop().time()
        if delay > 0:
            try:
                await asyncio.wait_for(playback_interrupt_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass
        return playback_is_current(generation)

    async def stream_pcm_to_exotel(pcm_bytes: bytes, generation: int):
        """Enqueue Sarvam PCM bytes to be sent in fixed 100ms frames."""
        nonlocal stream_sid, is_closed
        if not stream_sid or is_closed or not playback_is_current(generation):
            return
        await exotel_pcm_queue.put((generation, pcm_bytes))

    async def wait_for_exotel_playback_done(generation: int, exotel_playback_done: asyncio.Event) -> bool:
        """Wait for this playback's final queued PCM frame, unless interrupted."""
        await exotel_playback_done.wait()
        return playback_is_current(generation)

    async def exotel_sender_task_loop():
        """Dedicated task to buffer and send 100ms PCM frames continuously."""
        nonlocal stream_sid, is_closed, debug_exotel_logged_first_chunk, first_media_logged
        nonlocal exotel_next_send_time, exotel_pcm_buffer, exotel_buffer_generation
        
        # 16000 Hz * 2 bytes * 0.10 sec = 3200 bytes
        chunk_size_40ms = int(sample_rate * 2 * 0.04)
        loop = asyncio.get_event_loop()
        
        while not is_closed:
            try:
                # Wait for data or flush signal with a short timeout to allow checking is_closed
                generation, chunk = await asyncio.wait_for(exotel_pcm_queue.get(), timeout=0.01)
                if not playback_is_current(generation):
                    continue
                
                if chunk == b"":
                    # Flush signal: if we have residual data, pad and send it
                    if len(exotel_pcm_buffer) > 0:
                        pad_len = chunk_size_40ms - len(exotel_pcm_buffer)
                        exotel_pcm_buffer.extend(b"\x00" * pad_len)
                        
                        if not await wait_for_playback_slot(exotel_next_send_time, generation):
                            exotel_pcm_buffer.clear()
                            continue
                        now = loop.time()
                        
                        chunk_data = bytes(exotel_pcm_buffer[:chunk_size_40ms])
                        exotel_pcm_buffer.clear()
                        
                        try:
                            if not is_closed and playback_is_current(generation):
                                payload = json.dumps({
                                    "event": "media",
                                    "stream_sid": stream_sid,
                                    "media": {"payload": base64.b64encode(chunk_data).decode("utf-8")}
                                }, separators=(",", ":"))
                                await websocket.send_text(payload)
                                record_sent(chunk_data)
                        except Exception as e:
                            import traceback
                            print(f"[sender_loop block 1 ERROR] {e}")
                            traceback.print_exc()
                            invalidate_playback()
                            continue
                            
                        exotel_next_send_time = now + 0.04
                    # The end marker reaches this point only after every
                    # complete frame plus any padded residual frame was sent.
                    if playback_is_current(generation):
                        finish_exotel_playback(generation)
                elif chunk:
                    now = loop.time()
                    if len(exotel_pcm_buffer) and exotel_buffer_generation != generation:
                        exotel_pcm_buffer.clear()
                    # If this is a fresh start (buffer was empty and scheduling is behind)
                    if len(exotel_pcm_buffer) == 0 and exotel_next_send_time < now:
                        # ~100ms jitter buffer before starting playback
                        exotel_next_send_time = now + 0.100
                    exotel_buffer_generation = generation
                    exotel_pcm_buffer.extend(chunk)
                    
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                print(f"Error receiving websocket msg: {e}")
                
            # Send all complete 100ms frames
            while len(exotel_pcm_buffer) >= chunk_size_40ms:
                generation = exotel_buffer_generation
                if not playback_is_current(generation):
                    exotel_pcm_buffer.clear()
                    break
                now = loop.time()
                # If we're ahead of the pacing schedule, wait for the exact moment
                if not await wait_for_playback_slot(exotel_next_send_time, generation):
                    exotel_pcm_buffer.clear()
                    break
                now = loop.time()
                
                chunk_data = bytes(exotel_pcm_buffer[:chunk_size_40ms])
                del exotel_pcm_buffer[:chunk_size_40ms]
                
                try:
                    if not is_closed and playback_is_current(generation):
                        if not first_media_logged:
                            print(f"[{get_boundary_ts()}] [Boundary] Exotel first media packet SENT")
                            first_media_logged = True
                        if not turn_metrics.get("exotel_first_audio_sent") and "speech_start" in turn_metrics:
                            turn_metrics["exotel_first_audio_sent"] = loop.time()
                            print_latency_block(turn_metrics)
                        payload = json.dumps({
                            "event": "media",
                            "stream_sid": stream_sid,
                            "media": {"payload": base64.b64encode(chunk_data).decode("utf-8")}
                        }, separators=(",", ":"))
                        await websocket.send_text(payload)
                        record_sent(chunk_data)
                except Exception as e:
                    import traceback
                    print(f"[sender_loop block 2 ERROR] {e}")
                    traceback.print_exc()
                    invalidate_playback()
                    break
                    
                if not debug_exotel_logged_first_chunk:
                    debug_exotel_logged_first_chunk = True
                
                # Advance next_send_time exactly by 100ms
                exotel_next_send_time += 0.04

    # Booking Script State Machine (Call Session Level)
    
    booking_details = {}

    async def run_ai_tts_pipeline(text: str, is_system_prompt: bool = False):
        turn_metrics["gemini_start"] = asyncio.get_event_loop().time()
        """Full streaming pipeline: text → Gemini stream → Sarvam TTS WS stream → Exotel PCM"""
        nonlocal stream_sid, is_closed, call_sid, bot_speaking, bot_finished_at, silence_prompt_active
        user_id = call_sid or "default_user"
        bot_speaking = True
        bot_finished_at = None
        silence_prompt_active = False
        playback_id, exotel_playback_done = begin_playback()
        playback_end_enqueued = False

        async def send_response_complete_after_playback() -> bool:
            """Put the mark behind this response's final sender-drained frame."""
            nonlocal playback_end_enqueued
            if not playback_end_enqueued:
                await stream_pcm_to_exotel(b"", playback_id)
                playback_end_enqueued = True
            if not await wait_for_exotel_playback_done(playback_id, exotel_playback_done):
                return False
            await send_mark("response_complete")
            exotel_playback_done_events.pop(playback_id, None)
            
            async def watchdog():
                await asyncio.sleep(5.0)
                nonlocal bot_speaking, bot_finished_at, silence_prompt_active
                if bot_speaking and playback_is_current(playback_id):
                    print(f"[{get_boundary_ts()}] [Boundary] Response complete mark lost. Watchdog forcing bot_speaking=False")
                    bot_speaking = False
                    bot_finished_at = asyncio.get_event_loop().time()
                    silence_prompt_active = False
            asyncio.create_task(watchdog())
            return True
        
        pipeline_start_time = asyncio.get_event_loop().time()
        

        print(f"[{get_boundary_ts()}] [Boundary] Gemini request")
        
        first_gemini_token_time = None
        first_audio_chunk_time = None
        text_for_ai = text
        
        async def _play_delayed_filler():
            await asyncio.sleep(0.1)
            if is_closed or not playback_is_current(playback_id):
                return
            if first_audio_chunk_time is None:
                if sample_rate in _short_fillers_cache and _short_fillers_cache[sample_rate]:
                    import random
                    filler_pcm = random.choice(_short_fillers_cache[sample_rate])
                    print(f"[{get_boundary_ts()}] [Boundary] TTFT > 0.1s, playing pre-cached audio filler!")
                    await stream_pcm_to_exotel(filler_pcm, playback_id)
                else:
                    print(f"[{get_boundary_ts()}] [Boundary] Filler failed: Cache empty for {sample_rate}Hz!")

        asyncio.create_task(_play_delayed_filler())
        
        
            
        # Standard Route: Gemini AI & Sarvam TTS Streaming
        if not is_system_prompt:
            memory_manager.save_interaction(user_id, "user", text)
        history = memory_manager.get_history(user_id)
        gemini_history = history[:-1] if len(history) > 0 else []
        full_response = ""
        should_hang_up = False

        try:
            async def gemini_text_generator():
                nonlocal full_response, first_gemini_token_time, should_hang_up
                stream = ai_service.generate_response_stream(text_for_ai, gemini_history)
                try:
                    async for chunk_text in stream:
                        if chunk_text == "hang_up":
                            should_hang_up = True
                            break
                        if first_gemini_token_time is None:
                            print(f"[{get_boundary_ts()}] [Boundary] Gemini first token")
                            first_gemini_token_time = asyncio.get_event_loop().time()
                            turn_metrics["gemini_first_token"] = first_gemini_token_time
                            ttft = first_gemini_token_time - pipeline_start_time
                            print(f"[Timing] Step 3 Text Gen (TTFT): {ttft:.2f}s")
                        full_response += chunk_text
                        yield chunk_text
                except Exception as e:
                    import traceback
                    print(f"[{get_boundary_ts()}] [Error] Generator failed: {e}")
                    traceback.print_exc()

            # Pipe Gemini stream into Sarvam TTS
            # Pipe Gemini stream into Sarvam TTS

            # DEBUG: collect raw Sarvam TTS audio
            debug_tts_audio = bytearray()
            
            sent_tts_text_logged = False
            async def logged_gemini_generator():
                nonlocal sent_tts_text_logged
                async for chunk in gemini_text_generator():
                    if not sent_tts_text_logged and chunk.strip():
                        print(f"[{get_boundary_ts()}] [Boundary] TTS text sent")
                        turn_metrics["tts_start"] = asyncio.get_event_loop().time()
                        sent_tts_text_logged = True
                    yield chunk

            from services.speech.text_chunker import chunk_for_tts
            async for pcm_chunk in tts_service.stream_tts(
                chunk_for_tts(logged_gemini_generator()),
                language_code="hi-IN",
                pace=1.0,
                speech_sample_rate=sample_rate,
                pipeline_start_time=pipeline_start_time
            ):
                try:
                    if first_audio_chunk_time is None:
                        first_audio_chunk_time = asyncio.get_event_loop().time()
                        turn_metrics["tts_first_audio"] = first_audio_chunk_time
                    print(f"[Sarvam TTS Debug] Returned chunk: {len(pcm_chunk)} bytes (S16LE, Mono, 16000 Hz)")
                    sarvam_audio.extend(pcm_chunk)
                except:
                    pass

                if first_audio_chunk_time is None:
                    print(f"[{get_boundary_ts()}] [Boundary] Sarvam first audio")
                    first_audio_chunk_time = asyncio.get_event_loop().time()
                    nonlocal current_pipeline_audio_sent
                    current_pipeline_audio_sent = True
                    audio_latency = first_audio_chunk_time - pipeline_start_time
                    print(f"[Timing] Step 4 Exotel First Audio Sent: {audio_latency:.2f}s")

                # SAVE RAW SARVAM PCM
                debug_tts_audio.extend(pcm_chunk)

                # Normal audio flow to Exotel
                await stream_pcm_to_exotel(pcm_chunk, playback_id)
            await stream_pcm_to_exotel(b"", playback_id)
            playback_end_enqueued = True
            print(f"[Timing] Step 5 Full TTS Audio Completed: {(asyncio.get_event_loop().time() - pipeline_start_time):.2f}s")


            # ==========================================
            # DEBUG: SAVE RAW SARVAM AUDIO AS WAV

            if not await send_response_complete_after_playback():
                return
            memory_manager.save_interaction(user_id, "assistant", full_response)
            
            total_duration = asyncio.get_event_loop().time() - pipeline_start_time
            
            if should_hang_up:
                # Wait for Exotel to actually finish playing the audio (ACK the mark) before slicing the connection
                while bot_speaking and playback_is_current(playback_id):
                    await asyncio.sleep(0.1)
                await websocket.close()
                return

        except asyncio.CancelledError:
            if playback_is_current(playback_id):
                invalidate_playback()
            exotel_playback_done_events.pop(playback_id, None)
            bot_speaking = False
            if full_response.strip():
                memory_manager.save_interaction(user_id, "assistant", full_response + "...")
            raise
        except Exception as e:
            import traceback
            print(f"Exception in run_ai_tts_pipeline: {e}")
            traceback.print_exc()

            if not await send_response_complete_after_playback():
                return
            memory_manager.save_interaction(user_id, "assistant", full_response)
            
            total_duration = asyncio.get_event_loop().time() - pipeline_start_time
            
            if should_hang_up:
                # Wait for Exotel to actually finish playing the audio (ACK the mark) before slicing the connection
                while bot_speaking and playback_is_current(playback_id):
                    await asyncio.sleep(0.1)
                await websocket.close()
                return

    async def process_after_silence():
        nonlocal latest_transcript, last_transcript_time, current_pipeline_audio_sent, current_pipeline_text, stream_sid, is_closed, response_task, user_currently_speaking, bot_finished_at, silence_prompt_active
        
        while not is_closed:
            await asyncio.sleep(0.05)
            current_time = asyncio.get_event_loop().time()
            
            # Never evaluate silence while either party is speaking or an
            # assistant response/greeting remains active.
            if (bot_speaking or greeting_playing or user_currently_speaking or
                    (response_task and not response_task.done()) or
                    (greeting_task and not greeting_task.done())):
                continue

            if latest_transcript:
                silence_duration = current_time - last_transcript_time
                # Trigger response if:
                # 1. User stopped speaking and silence duration > 0.3s
                # 2. Or fallback limit of 1.5s hit (in case of missing VAD speech_end packet)
                if (not user_currently_speaking and silence_duration > 0.3) or (silence_duration > 1.5):
                    print(f"[{get_boundary_ts()}] [Boundary] STT final transcript")
                    turn_metrics["stt_final"] = current_time
                    final_text = latest_transcript.strip()
                    latest_transcript = "" 
                    user_currently_speaking = False
                    
                
                    if response_task and not response_task.done():
                        response_task.cancel()
                        try:
                            await response_task
                        except asyncio.CancelledError:
                            pass
                        
                    response_task = asyncio.create_task(run_ai_tts_pipeline(final_text))
                continue

            # Start the idle countdown only after Exotel acknowledges that the
            # current bot playback has completed. A prompt fires once per turn.
            if (bot_finished_at is not None and not silence_prompt_active and
                    current_time - bot_finished_at >= 10.0):
                silence_prompt_active = True
                silence_prompt = "[SYSTEM] The user has been completely silent for 11 seconds. Ask them if they are still there on the line in a short, natural way (e.g. 'Hello? Are you there?'), matching the language of the conversation."
                response_task = asyncio.create_task(run_ai_tts_pipeline(silence_prompt, is_system_prompt=True))

    sarvam_task = asyncio.create_task(handle_sarvam_responses())
    silence_task = asyncio.create_task(process_after_silence())
    exotel_sender_task = asyncio.create_task(exotel_sender_task_loop())

    first_media_logged = False
    try:
        while True:
            result = await websocket.receive()
            
            if result["type"] == "websocket.disconnect":
                break
                
            if result["type"] == "websocket.receive":
                if "text" in result:
                    data = result["text"]
                    message = json.loads(data)
                    event = message.get("event")
                    
                    if event == "connected":
                        pass
                    
                    elif event == "start":
                        print(f"============================================================")
                        print(f"[Exotel WS] Received 'start' event from Exotel.")
                        print(f"[Exotel WS] Exact Start Message: {json.dumps(message, indent=2)}")
                        print(f"============================================================")
                        
                        sent_end_time = asyncio.get_event_loop().time()
                        stream_sid = message.get("stream_sid") or message.get("streamSid") or message.get("start", {}).get("stream_sid")
                        
                        call_sid = (
                            message.get("start", {}).get("callSid") 
                            or message.get("start", {}).get("call_sid") 
                            or message.get("callSid") 
                            or message.get("call_sid")
                            or websocket.query_params.get("CallSid")
                            or websocket.query_params.get("call_sid")
                            or stream_sid
                            or f"mock_{int(asyncio.get_event_loop().time())}"
                        )
                        call_start_time = asyncio.get_event_loop().time()
                        
                        if call_sid in force_terminated_calls:
                            await websocket.close()
                            return

                        # Register the websocket so we can terminate it later
                        if call_sid:
                            active_exotel_websockets[call_sid] = websocket
                        
                        from_num = (
                            websocket.query_params.get("From") 
                            or websocket.query_params.get("from") 
                            or message.get("start", {}).get("customParameters", {}).get("From")
                            or message.get("start", {}).get("customParameters", {}).get("from")
                        )
                        to_num = (
                            websocket.query_params.get("To") 
                            or websocket.query_params.get("to") 
                            or message.get("start", {}).get("customParameters", {}).get("To")
                            or message.get("start", {}).get("customParameters", {}).get("to")
                        )
                        direction = (
                            websocket.query_params.get("Direction") 
                            or websocket.query_params.get("direction") 
                            or "incoming"
                        )
                        
                        # Initialize call log in PostgreSQL
                        asyncio.create_task(initialize_call_log(
                            call_sid=call_sid,
                            stream_sid=stream_sid,
                            direction=direction,
                            from_num=from_num,
                            to_num=to_num
                        ))
                        
                        # Extract sample_rate dynamically from media_format in start event if present
                        media_format = message.get("start", {}).get("media_format", {})
                        if media_format:
                            rate_str = media_format.get("sample_rate")
                            if rate_str:
                                try:
                                    sample_rate = int(rate_str)
                                    frame_size_20ms = int(sample_rate * 2 * 0.02)
                                except ValueError:
                                    pass
                                # ========================================
                        # DEBUG: Confirm actual Exotel audio format
                        # ========================================

                        # Pre-cache all scripted replies in background at this sample rate (Priority 4)
                        for reply in SCRIPTED_REPLIES:
                            asyncio.create_task(_ensure_fast_path_cached(reply, sample_rate))
                        

                        greeting_playing = True
                        greeting_task = asyncio.create_task(send_greeting())
                    
                    elif event == "media":
                            
                        payload = message.get("media", {}).get("payload")
                        if payload:
                            if not first_media_logged:
                                first_media_logged = True
                            # Convert source sample rate to 16kHz PCM for Sarvam
                            audio_bytes = audio_processor.exotel_pcm_to_sarvam_pcm(payload, source_sample_rate=sample_rate)
                            await audio_queue.put(audio_bytes)
                    
                    elif event == "stop":
                        is_closed = True
                        if greeting_task and not greeting_task.done():
                            greeting_task.cancel()
                        break

                    elif event == "mark":
                        mark_name = message.get("mark", {}).get("name", "")
                        if mark_name == "response_complete":
                            print(f"[{get_boundary_ts()}] [Boundary] Audio playback completed (Exotel Ack)")
                            bot_speaking = False
                            bot_finished_at = asyncio.get_event_loop().time()
                            silence_prompt_active = False
                            if not user_currently_speaking:
                                latest_transcript = ""

                    elif event == "clear":
                        invalidate_playback()
                        if greeting_playing and greeting_task and not greeting_task.done():
                            greeting_task.cancel()
                            greeting_playing = False
                        if response_task and not response_task.done():
                            response_task.cancel()
                            bot_speaking = False
                
                elif "bytes" in result:
                    if not first_media_logged:
                        first_media_logged = True
                    # Treat binary with source sample rate to 16kHz conversion
                    audio_bytes = audio_processor.exotel_pcm_to_sarvam_pcm_raw(result["bytes"], source_sample_rate=sample_rate)
                    await audio_queue.put(audio_bytes)
                    
    except Exception as e:
        import traceback
        print(f"[exotel_ws_endpoint MAIN LOOP ERROR] {e}")
        traceback.print_exc()
    finally:
        is_closed = True
        invalidate_playback()
        await audio_queue.put(None)
        
        if greeting_task and not greeting_task.done():
            greeting_task.cancel()
        if response_task and not response_task.done():
            response_task.cancel()
        if not sarvam_task.done():
            sarvam_task.cancel()
        if 'exotel_sender_task' in locals() and not exotel_sender_task.done():
            exotel_sender_task.cancel()
        if 'silence_task' in locals() and not silence_task.done():
            silence_task.cancel()
            
        # Save final call log details to database
        if call_sid:
            duration = 0
            if call_start_time:
                duration = int(asyncio.get_event_loop().time() - call_start_time)
            
            history_msgs = []
            try:
                history_msgs = memory_manager.get_history(call_sid or "default_user", limit=50)
            except Exception as e:
                print(f"Error receiving websocket msg: {e}")
                
            asyncio.create_task(finalize_call_log(
                call_sid=call_sid,
                duration=duration,
                history_messages=history_msgs
            ))
            
        
        # Cleanup registry
        if call_sid and call_sid in active_exotel_websockets:
            active_exotel_websockets.pop(call_sid, None)
            
        # Resilient channel release in case webhook is delayed or dropped
        if call_sid:
            try:
                from services.telephony.channel_manager import ChannelManager
                from services.telephony.queue_dispatcher import QueueDispatcher
                cm = ChannelManager()
                dispatcher = QueueDispatcher()
                released = await cm.release_channel_by_sid(call_sid)
                if released:
                    asyncio.create_task(dispatcher.dispatch())
            except Exception as release_err:
                print(f"[Exotel WS Cleanup Error]: {release_err}")

        # Final Debug Audio Saving
        if call_sid and DEBUG_AUDIO:
            def _save_call_audio(audio_buffer, filename):
                if not audio_buffer:
                    return
                try:
                    filepath = os.path.join(DEBUG_AUDIO_DIR, filename)
                    os.makedirs(DEBUG_AUDIO_DIR, exist_ok=True)
                    import wave
                    with wave.open(filepath, "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(sample_rate)
                        wf.writeframes(bytes(audio_buffer))
                    print(f"[Audio Dump] Saved: {filepath} ({len(audio_buffer)} bytes)")
                except Exception as e:
                    print(f"[Audio Dump Error] Failed to save {filename}: {e}")

            
            save_tasks = []
            if 'sarvam_audio' in locals():
                save_tasks.append(asyncio.to_thread(_save_call_audio, sarvam_audio, f"sarvam_{call_sid}.wav"))
            if 'sent_audio' in locals():
                save_tasks.append(asyncio.to_thread(_save_call_audio, sent_audio, f"exotel_{call_sid}.wav"))
            
            if save_tasks:
                await asyncio.gather(*save_tasks)