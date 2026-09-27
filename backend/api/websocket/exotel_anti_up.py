import json

def detect_sarvam_language(user_text: str) -> str:
    user_text_lower = user_text.lower()
    if any(2304 <= ord(c) <= 2431 for c in user_text):
        return "hi-IN"
    hinglish_keywords = {"hai", "kya", "haan", "nahi", "mein", "mera", "mujhe", "aap", "kaise", "theek", "ji", "koi"}
    words = set(user_text_lower.split())
    if words.intersection(hinglish_keywords):
        return "hi-IN"
    return "en-IN"

import os
import base64
import asyncio
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
        
        print(f"\n{'='*50}")
        print(f"⚠️ [EXOTEL CALL STATUS REPORT]")
        print(f"Call SID: {call_sid}")
        print(f"Phone Number (From): {from_number}")
        print(f"Phone Number (To): {to_number}")
        print(f"Final Status: {status.upper()}")
        print(f"Raw Payload: {dict(form_data)}")
        print(f"{'='*50}\n")
        
        # --- Channel Queue Manager Integration ---
        from services.telephony.channel_manager import ChannelManager
        from services.telephony.queue_dispatcher import QueueDispatcher

        channel_manager = ChannelManager()
        dispatcher = QueueDispatcher()

        # Try to release the channel if this CallSid matches
        released_channel_id = await channel_manager.release_channel_by_sid(call_sid)
        
        if released_channel_id:
            print(f"[Exotel Status Callback] Released channel {released_channel_id} for CallSid {call_sid}")
            # Immediately assign the next waiting lead from the queue
            asyncio.create_task(dispatcher.dispatch())
        else:
            print(f"[Exotel Status Callback] Ignored channel release. CallSid {call_sid} does not belong to any active channel.")

        # --- Finalize Call Log for Non-WS Call (Failed/Busy calls before WS starts) ---
        if status.lower() not in ["in-progress", "ringing"]:
            if call_sid not in active_exotel_websockets:
                print(f"[Exotel Status Callback] Final state '{status}' received for CallSid {call_sid} with no active WS. Finalizing call log.")
                asyncio.create_task(finalize_call_log(
                    call_sid=call_sid,
                    duration=0,
                    history_messages=[]
                ))

        return {"status": "success"}
    except Exception as e:
        print(f"[Exotel Status Callback Error]: {e}")
        return {"status": "error"}

# Global registry for active websockets so we can forcefully terminate them
active_exotel_websockets: dict[str, WebSocket] = {}
force_terminated_calls = set()

# Lazy cache mapped by sample_rate: {8000: [...], 16000: [...], 24000: [...]}
_greeting_chunks_cache: dict[str, dict[int, list[str]]] = {"inbound": {}, "outbound": {}}
_greeting_cache_lock = asyncio.Lock()
_INBOUND_GREETING_TEXT = "नमस्ते, मैं रितु बोल रही हूँ, क्विक स्पेस से। मैं आपकी कैसे मदद कर सकती हूँ?"
_OUTBOUND_GREETING_TEXT = "नमस्ते, मैं रितु बोल रही हूँ क्विक स्पेस से। आपने हमारी वेबसाइट पर इंक्वायरी की थी, क्या अभी आपसे 2 मिनट बात हो सकती है?"
async def _ensure_greeting_cached(direction: str, sample_rate: int):
    """Generate greeting audio once per sample rate and cache it. Thread-safe."""
    global _greeting_chunks_cache
    text = "नमस्ते, मैं रितु बोल रही हूँ, क्विक स्पेस से। मैं आपकी कैसे मदद कर सकती हूँ?" if direction == "inbound" else "नमस्ते, मैं रितु बोल रही हूँ क्विक स्पेस से। आपने हमारी वेबसाइट पर इंक्वायरी की थी, क्या अभी आपसे 2 मिनट बात हो सकती है?"
    cache_dict = _greeting_chunks_cache[direction]
    
    if sample_rate in cache_dict:
        return  # Already cached for this rate

    async with _greeting_cache_lock:
        if sample_rate in cache_dict:  # Double-check
            return

        tts_service = SarvamTTSService()
        audio_processor = AudioProcessor()
        import audioop

        print(f"[Greeting Cache] First call for {direction} at {sample_rate}Hz — generating greeting...")
        audio_b64_raw = await tts_service.synthesize_realtime(text, speech_sample_rate=sample_rate)
        if not audio_b64_raw:
            print("[Greeting Cache] WARNING: Failed to generate greeting audio")
            return

        # Resample and convert to raw PCM for this specific sample rate
        audio_b64_pcm = audio_processor.wav_to_exotel_pcm(audio_b64_raw, target_sample_rate=sample_rate)
        audio_bytes = base64.b64decode(audio_b64_pcm)

        # Dynamic silence threshold based on sample rate
        # 320 bytes = 20ms @ 8kHz (16-bit)
        # For sample_rate: 20ms frame = sample_rate * 2 * 0.02
        frame_size_20ms = int(sample_rate * 2 * 0.02)

        while len(audio_bytes) > frame_size_20ms and audioop.rms(audio_bytes[:frame_size_20ms], 2) < 5:
            audio_bytes = audio_bytes[frame_size_20ms:]

        # 100ms chunk sizes dynamically calculated per sample rate
        chunk_size = int(sample_rate * 2 * 0.10)  # 100ms
        chunks = []
        for i in range(0, len(audio_bytes), chunk_size):
            chunk_data = audio_bytes[i:i + chunk_size]
            if len(chunk_data) % frame_size_20ms != 0:
                pad = frame_size_20ms - (len(chunk_data) % frame_size_20ms)
                chunk_data = chunk_data + b'\x00' * pad
            chunks.append(base64.b64encode(chunk_data).decode('utf-8'))

        _greeting_chunks_cache[sample_rate] = chunks
        print(f"[Greeting Cache] Cached {len(chunks)} chunks at {sample_rate}Hz.")

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

        print(f"[Fast-Path Cache] Caching text '{text[:30]}...' at {sample_rate}Hz...")
        audio_b64_raw = await tts_service.synthesize_realtime(text, speech_sample_rate=sample_rate)
        if not audio_b64_raw:
            print(f"[Fast-Path Cache] Failed to generate audio for: '{text[:20]}'")
            return

        # Resample and convert to raw PCM for this specific sample rate
        audio_b64_pcm = audio_processor.wav_to_exotel_pcm(audio_b64_raw, target_sample_rate=sample_rate)
        audio_bytes = base64.b64decode(audio_b64_pcm)

        frame_size_20ms = int(sample_rate * 2 * 0.02)
        while len(audio_bytes) > frame_size_20ms and audioop.rms(audio_bytes[:frame_size_20ms], 2) < 5:
            audio_bytes = audio_bytes[frame_size_20ms:]

        chunk_size = int(sample_rate * 2 * 0.10)  # 100ms chunks
        chunks = []
        for i in range(0, len(audio_bytes), chunk_size):
            chunk_data = audio_bytes[i:i + chunk_size]
            if len(chunk_data) % frame_size_20ms != 0:
                pad = frame_size_20ms - (len(chunk_data) % frame_size_20ms)
                chunk_data = chunk_data + b'\x00' * pad
            chunks.append(base64.b64encode(chunk_data).decode('utf-8'))

        _fast_path_cache[sample_rate][text] = chunks
        print(f"[Fast-Path Cache] Cached '{text[:30]}...' at {sample_rate}Hz.")


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
            print(f"[Exotel WS] Fired cancel requests to Exotel API for {call_sid}")
    except Exception as api_err:
        print(f"[Exotel WS] Error attempting to cancel via API: {api_err}")
    
    ws = active_exotel_websockets.get(call_sid)
    if ws:
        try:
            print(f"[Exotel WS] Force terminating call_sid: {call_sid}")
            await ws.close()
            active_exotel_websockets.pop(call_sid, None)
            return {"status": "success", "message": "Call terminated via WebSocket close."}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "success", "message": "Call marked for termination upon connection."}

@router.websocket("/exotel")
async def exotel_stream_handler(websocket: WebSocket):
    await websocket.accept()
    print("[Exotel WS] Voicebot Connection accepted")
    
    # ── Dynamic Sample Rate Extraction ──
    # Exotel passes `sample-rate=24000` or `sample_rate=24000` as query params. Default is 16000Hz if not specified.
    param_rate = websocket.query_params.get("sample-rate") or websocket.query_params.get("sample_rate") or "16000"
    try:
        sample_rate = int(param_rate)
    except ValueError:
        sample_rate = 16000
    print(f"[Exotel WS] Call streaming configured at {sample_rate}Hz")

    # Start caching greeting eagerly on connect to reduce start latency
    # asyncio.create_task(_ensure_greeting_cached(sample_rate)) # Disabled pre-cache since direction varies

    # Frame and Chunk parameters calculated dynamically
    frame_size_20ms = int(sample_rate * 2 * 0.02)  # Multiple check pad (20ms)
    chunk_size_100ms = int(sample_rate * 2 * 0.10)  # Playback chunk (100ms)

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
    audio_queue = asyncio.Queue()
    is_closed = False
    greeting_task = None
    greeting_playing = False
    response_task = None
    bot_speaking = False  # Flag: True when bot is actively playing audio
    
    # Debounce state
    latest_transcript = ""
    last_transcript_time = 0
    user_currently_speaking = False
    bot_finished_at = None
    silence_prompt_active = False
    debug_exotel_audio = bytearray()
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

    async def send_greeting(direction_type: str):
        nonlocal stream_sid, is_closed, greeting_playing
        
        if not stream_sid or is_closed:
            return

        playback_id, exotel_playback_done = begin_playback()
        print(f"[Exotel WS] Sending {direction_type} greeting to {stream_sid} at {sample_rate}Hz")
        try:
            # Dynamically ensure cached for target sample_rate
            await _ensure_greeting_cached(direction_type, sample_rate)
            if not playback_is_current(playback_id):
                return
            chunks = _greeting_chunks_cache[direction_type].get(sample_rate, [])
            await send_paced(chunks, playback_id)
            if playback_is_current(playback_id):
                exotel_playback_done.set()
            greeting_playing = False
            print(f"[Exotel WS] Greeting complete, now listening")
            text = "नमस्ते, मैं रितु बोल रही हूँ, क्विक स्पेस से। मैं आपकी कैसे मदद कर सकती हूँ?" if direction_type == "inbound" else "नमस्ते, मैं रितु बोल रही हूँ क्विक स्पेस से। आपने हमारी वेबसाइट पर इंक्वायरी की थी, क्या अभी आपसे 2 मिनट बात हो सकती है?"
            memory_manager.save_interaction(call_sid or "default_user", "assistant", text)
        except asyncio.CancelledError:
            exotel_playback_done.set()
            greeting_playing = False
            print("[Exotel WS] Greeting cancelled by barge-in")
            memory_manager.save_interaction(call_sid or "default_user", "assistant", "नमस्ते, मैं Priya बोल रही हूँ, Charaktaal Eco Village से...")
            raise
        except Exception as e:
            exotel_playback_done.set()
            greeting_playing = False
            print(f"[Exotel WS] Greeting send error: {e}")

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
            print("[BARGE-IN] Exotel clear sent")
        except Exception as e:
            print(f"[Exotel WS] Clear send error: {e}")

    async def stop_bot_playback_for_barge_in():
        """Invalidate stale audio before asking Exotel to clear its buffer."""
        nonlocal greeting_playing, bot_speaking

        # Cancel producers first, then invalidate their generation before any
        # local/external buffer operation. The permanent sender task remains
        # alive and rejects every old-generation item.
        bot_speaking = False
        if greeting_playing and greeting_task and not greeting_task.done():
            print("[BARGE-IN] cancelling greeting task")
            greeting_task.cancel()
            greeting_playing = False
        if response_task and not response_task.done():
            print("[BARGE-IN] cancelling response task")
            response_task.cancel()

        invalidate_playback()
        await send_clear()

    async def handle_sarvam_responses():
        nonlocal stream_sid, latest_transcript, last_transcript_time, response_task, greeting_task, greeting_playing, bot_speaking, user_currently_speaking
        try:
            async for result in stt_service.stream_transcription(audio_generator()):
                msg_type = result.get("type", "")

                # VAD: User STARTED speaking → stop bot playback immediately.
                # Do not wait for transcript recognition; it arrives too late for
                # natural barge-in behavior.
                if msg_type == "speech_start":
                    print("[BARGE-IN] speech_start detected")
                    user_currently_speaking = True
                    reset_post_bot_silence()
                    # Exotel can acknowledge a mark before the caller has
                    # audibly drained all remote media. Keep clear available
                    # for that post-mark playback window as well.
                    if bot_speaking or greeting_playing or playback_may_be_active:
                        print("[BARGE-IN] stopping playback")
                        await stop_bot_playback_for_barge_in()
                    continue

                # VAD: User STOPPED speaking → accelerate silence timer
                if msg_type == "speech_end":
                    print("[Exotel WS] VAD Speech End detected")
                    user_currently_speaking = False
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
                            print(f"[Exotel WS] Ignoring STT while bot speaking (echo/noise - no VAD): '{transcript}'")
                            continue
                        if len(cleaned_t) < 12 or len(cleaned_t) < 4 or cleaned_t in ignore_list:
                            print(f"[Exotel WS] Ignoring short/filler STT while bot speaking (VAD active): '{transcript}'")
                            continue
                        print(f"[Exotel WS] Strong barge-in detected while bot speaking: '{transcript}'")

                    # Robust Filter: Ignore transcripts < 4 characters or inside ignore list for active barge-in
                    if len(cleaned_t) >= 4 and cleaned_t not in ignore_list:
                        print(f"[Exotel WS] Transcript (barge-in active): {transcript}")
                        if latest_transcript:
                            latest_transcript += " " + transcript
                        else:
                            latest_transcript = transcript
                        last_transcript_time = asyncio.get_event_loop().time()
                        reset_post_bot_silence()

                        # FIX 2: Perform barge-in cancellation + clear Exotel buffer
                        if ((greeting_playing and greeting_task and not greeting_task.done()) or
                                (response_task and not response_task.done())):
                            print("[Exotel WS] Transcript Barge-in: cancelling active playback")
                            await stop_bot_playback_for_barge_in()
                    else:
                        print(f"[Exotel WS] Ignoring tiny/filler STT interruption: '{transcript}'")
                        # Accept it for standard processing only if AI is silent
                        if not greeting_playing and (response_task is None or response_task.done()):
                            if latest_transcript:
                                latest_transcript += " " + transcript
                            else:
                                latest_transcript = transcript
                            last_transcript_time = asyncio.get_event_loop().time()
                            reset_post_bot_silence()

                elif "error" in result:
                    print(f"[Exotel WS] Sarvam Error: {result.get('error')}")
        except Exception as e:
            print(f"[Exotel WS] Sarvam Handler Error: {e}")

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
            print(f"[Exotel WS] Mark sent: {mark_name}")
        except Exception as e:
            print(f"[Exotel WS] Mark send error: {e}")

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
        print("[BARGE-IN] local audio buffers cleared; old playback generation invalidated")

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
        nonlocal stream_sid, is_closed, debug_exotel_logged_first_chunk
        nonlocal exotel_next_send_time, exotel_pcm_buffer, exotel_buffer_generation
        
        # 16000 Hz * 2 bytes * 0.10 sec = 3200 bytes
        chunk_size_100ms = int(sample_rate * 2 * 0.10)
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
                        pad_len = chunk_size_100ms - len(exotel_pcm_buffer)
                        exotel_pcm_buffer.extend(b"\x00" * pad_len)
                        
                        if not await wait_for_playback_slot(exotel_next_send_time, generation):
                            exotel_pcm_buffer.clear()
                            continue
                        now = loop.time()
                        
                        chunk_data = bytes(exotel_pcm_buffer[:chunk_size_100ms])
                        exotel_pcm_buffer.clear()
                        
                        try:
                            if not is_closed and playback_is_current(generation):
                                payload = json.dumps({
                                    "event": "media",
                                    "stream_sid": stream_sid,
                                    "media": {"payload": base64.b64encode(chunk_data).decode("utf-8")}
                                }, separators=(",", ":"))
                                await websocket.send_text(payload)
                        except Exception as e:
                            print(f"[Exotel Sender] Final flush error: {e}")
                            invalidate_playback()
                            continue
                            
                        exotel_next_send_time = now + 0.10
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
                        # 200ms prebuffer
                        exotel_next_send_time = now + 0.200
                    exotel_buffer_generation = generation
                    exotel_pcm_buffer.extend(chunk)
                    
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                print(f"[Exotel Sender] Queue get error: {e}")
                
            # Send all complete 100ms frames
            while len(exotel_pcm_buffer) >= chunk_size_100ms:
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
                
                chunk_data = bytes(exotel_pcm_buffer[:chunk_size_100ms])
                del exotel_pcm_buffer[:chunk_size_100ms]
                
                try:
                    if not is_closed and playback_is_current(generation):
                        payload = json.dumps({
                            "event": "media",
                            "stream_sid": stream_sid,
                            "media": {"payload": base64.b64encode(chunk_data).decode("utf-8")}
                        }, separators=(",", ":"))
                        await websocket.send_text(payload)
                except Exception as e:
                    print(f"[Exotel Sender] Send error: {e}")
                    invalidate_playback()
                    break
                    
                if not debug_exotel_logged_first_chunk:
                    debug_exotel_logged_first_chunk = True
                    print("=" * 60)
                    print("[EXOTEL OUT] FIRST AUDIO CHUNK (100ms pacing)")
                    print(f"[EXOTEL OUT] bytes: {len(chunk_data)}")
                    print(f"[EXOTEL OUT] duration: {len(chunk_data) / (sample_rate * 2) * 1000:.1f} ms")
                    print(f"[EXOTEL OUT] sample_rate: {sample_rate}")
                    print("[EXOTEL OUT] channels: 1")
                    print("[EXOTEL OUT] sample_width: 2 bytes")
                    print("[EXOTEL OUT] format: PCM S16LE")
                    print("=" * 60)
                
                # Advance next_send_time exactly by 100ms
                exotel_next_send_time += 0.10

    # Booking Script State Machine (Call Session Level)
    
    booking_details = {}

    async def run_ai_tts_pipeline(text: str, is_system_prompt: bool = False):
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
            return True
        
        pipeline_start_time = asyncio.get_event_loop().time()
        

        # ── Standard Route: Gemini AI & Sarvam TTS Streaming ──
        if not is_system_prompt:
            memory_manager.save_interaction(user_id, "user", text)
        history = memory_manager.get_history(user_id)
        print(f"DEBUG: history length: {len(history)} for user {user_id}")
        for m in history:
            print(f"  - {m.role}: {m.text}")
        gemini_history = history[:-1] if len(history) > 0 else []
        full_response = ""
        
        first_gemini_token_time = None
        first_audio_chunk_time = None

        try:
            async def gemini_text_generator():
                nonlocal full_response, first_gemini_token_time
                async for chunk_text in ai_service.generate_response_stream(text, gemini_history, call_direction="outbound" if "outbound" in direction.lower() else "inbound"):
                    if first_gemini_token_time is None:
                        first_gemini_token_time = asyncio.get_event_loop().time()
                        ttft = first_gemini_token_time - pipeline_start_time
                        print(f"[Latency Profile] TTFT (Time to First Gemini Token): {ttft * 1000:.1f}ms")

                    full_response += chunk_text
                    # Forward each Gemini fragment immediately. Sarvam's
                    # min_buffer_size/max_chunk_length own speech buffering.
                    yield chunk_text

            # Pipe Gemini stream into Sarvam TTS
            # Pipe Gemini stream into Sarvam TTS

            # DEBUG: collect raw Sarvam TTS audio
            debug_tts_audio = bytearray()

            async for pcm_chunk in tts_service.stream_tts(
                gemini_text_generator(),
                language_code=detect_sarvam_language(text),
                pace=1.0,
                speech_sample_rate=sample_rate
            ):
                if first_audio_chunk_time is None:
                    first_audio_chunk_time = asyncio.get_event_loop().time()
                    audio_latency = first_audio_chunk_time - pipeline_start_time
                    print(
                        f"[Latency Profile] Audio Latency "
                        f"(Time to first TTS audio packet): {audio_latency * 1000:.1f}ms"
                    )

                # SAVE RAW SARVAM PCM
                debug_tts_audio.extend(pcm_chunk)

                # Normal audio flow to Exotel
                await stream_pcm_to_exotel(pcm_chunk, playback_id)
            await stream_pcm_to_exotel(b"", playback_id)
            playback_end_enqueued = True


            # ==========================================
            # DEBUG: SAVE RAW SARVAM AUDIO AS WAV
            # ==========================================
            if debug_tts_audio:
                debug_path = f"/tmp/sarvam_{call_sid}.wav"

                with wave.open(debug_path, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)       # Linear16 = 16-bit
                    wf.setframerate(sample_rate)
                    wf.writeframes(bytes(debug_tts_audio))

                print(
                    f"[DEBUG] RAW SARVAM AUDIO SAVED: {debug_path} "
                    f"({len(debug_tts_audio)} bytes, {sample_rate}Hz)"
                )
                # ==========================================
            # DEBUG: SAVE EXACT PCM SENT TO EXOTEL
            # ==========================================
            if debug_exotel_audio and call_sid:
                try:
                    exotel_debug_path = f"/tmp/exotel_{call_sid}.wav"

                    with wave.open(exotel_debug_path, "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(sample_rate)
                        wf.writeframes(bytes(debug_exotel_audio))

                    print(
                        f"[DEBUG] EXACT EXOTEL AUDIO SAVED: "
                        f"{exotel_debug_path} "
                        f"({len(debug_exotel_audio)} bytes, {sample_rate}Hz)"
                    )

                except Exception as e:
                    print(f"[DEBUG] Failed to save Exotel audio: {e}")

            if not await send_response_complete_after_playback():
                return
            memory_manager.save_interaction(user_id, "assistant", full_response)
            
            total_duration = asyncio.get_event_loop().time() - pipeline_start_time
            print(f"[Latency Profile] Complete turn execution time: {total_duration * 1000:.1f}ms")
            print(f"[Exotel WS] Streaming response complete: {full_response[:80]}...")

        except asyncio.CancelledError:
            print("[Exotel WS] run_ai_tts_pipeline cancelled (barge-in)")
            if playback_is_current(playback_id):
                invalidate_playback()
            exotel_playback_done_events.pop(playback_id, None)
            bot_speaking = False
            if full_response.strip():
                memory_manager.save_interaction(user_id, "assistant", full_response + "...")
            raise
        except Exception as e:
            print(f"[AI/TTS STREAM ERROR] {e}")

            if not await send_response_complete_after_playback():
                return
            memory_manager.save_interaction(user_id, "assistant", full_response)
            
            total_duration = asyncio.get_event_loop().time() - pipeline_start_time
            print(f"[Latency Profile] Complete turn execution time: {total_duration * 1000:.1f}ms")
            print(f"[Exotel WS] Streaming response complete: {full_response[:80]}...")

    async def process_after_silence():
        nonlocal latest_transcript, last_transcript_time, stream_sid, is_closed, response_task, user_currently_speaking, bot_finished_at, silence_prompt_active
        
        while not is_closed:
            await asyncio.sleep(0.3)
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
                # 1. User stopped speaking and silence duration > 450ms
                # 2. Or fallback limit of 1.5s hit (in case of missing VAD speech_end packet)
                if (not user_currently_speaking and silence_duration > 0.75) or (silence_duration > 1.8):
                    final_text = latest_transcript.strip()
                    latest_transcript = "" 
                    user_currently_speaking = False
                    
                    print(f"[Exotel WS] Final user said: {final_text}")
                
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
                print("[Exotel WS] 10s post-playback silence detected. Prompting user.")
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
                print("[Exotel WS] WebSocket Disconnected")
                break
                
            if result["type"] == "websocket.receive":
                if "text" in result:
                    data = result["text"]
                    message = json.loads(data)
                    event = message.get("event")
                    
                    if event == "connected":
                        print("[Exotel WS] Event: Connected")
                    
                    elif event == "start":
                        print(f"[Exotel WS] Event: Start, Message: {data}")
                        stream_sid = message.get("stream_sid") or message.get("streamSid") or message.get("start", {}).get("stream_sid")
                        print(f"[Exotel WS] StreamSid set to: {stream_sid}")
                        
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
                            print(f"[Exotel WS] Call {call_sid} was force terminated early. Dropping connection instantly.")
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
                                    chunk_size_200ms = int(sample_rate * 2 * 0.20)
                                    print(f"[Exotel WS] Dynamic sample rate updated from media_format: {sample_rate}Hz")
                                except ValueError:
                                    pass
                                # ========================================
                        # DEBUG: Confirm actual Exotel audio format
                        # ========================================
                        print("========================================")
                        print("[Exotel WS] MEDIA FORMAT:", media_format)
                        print("[Exotel WS] ACTUAL SAMPLE RATE:", sample_rate)
                        print("========================================")

                        # Pre-cache all scripted replies in background at this sample rate (Priority 4)
                        for reply in SCRIPTED_REPLIES:
                            asyncio.create_task(_ensure_fast_path_cached(reply, sample_rate))

                        greeting_playing = True
                        greeting_type = "outbound" if "outbound" in direction.lower() else "inbound"
                        greeting_task = asyncio.create_task(send_greeting(greeting_type))
                    
                    elif event == "media":
                            
                        payload = message.get("media", {}).get("payload")
                        if payload:
                            if not first_media_logged:
                                print(f"[Exotel WS] Receiving media (Text/JSON) from Exotel for {stream_sid}...")
                                first_media_logged = True
                            # Convert source sample rate to 16kHz PCM for Sarvam
                            audio_bytes = audio_processor.exotel_pcm_to_sarvam_pcm(payload, source_sample_rate=sample_rate)
                            await audio_queue.put(audio_bytes)
                    
                    elif event == "stop":
                        print(f"[Exotel WS] Event: Stop, Message: {data}")
                        is_closed = True
                        if greeting_task and not greeting_task.done():
                            greeting_task.cancel()
                        break

                    elif event == "mark":
                        mark_name = message.get("mark", {}).get("name", "")
                        print(f"[Exotel WS] Mark acknowledged: {mark_name}")
                        if mark_name == "response_complete":
                            bot_speaking = False
                            bot_finished_at = asyncio.get_event_loop().time()
                            silence_prompt_active = False
                            if not user_currently_speaking:
                                latest_transcript = ""
                                print("[Exotel WS] Cleared stale transcript after bot finished speaking")

                    elif event == "clear":
                        print("[Exotel WS] Clear event: User interrupted (barge-in from Exotel)")
                        invalidate_playback()
                        if greeting_playing and greeting_task and not greeting_task.done():
                            greeting_task.cancel()
                            greeting_playing = False
                        if response_task and not response_task.done():
                            response_task.cancel()
                            bot_speaking = False
                            print("[Exotel WS] Barge-in: AI response cancelled via clear event")
                
                elif "bytes" in result:
                    if not first_media_logged:
                        print(f"[Exotel WS] Receiving media (Binary) from Exotel for {stream_sid}...")
                        first_media_logged = True
                    # Treat binary with source sample rate to 16kHz conversion
                    audio_bytes = audio_processor.exotel_pcm_to_sarvam_pcm_raw(result["bytes"], source_sample_rate=sample_rate)
                    await audio_queue.put(audio_bytes)
                    
    except Exception as e:
        print(f"[Exotel WS] Error in loop: {e}")
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
                print(f"[Exotel WS] Error retrieving final conversation history: {e}")
                
            asyncio.create_task(finalize_call_log(
                call_sid=call_sid,
                duration=duration,
                history_messages=history_msgs
            ))
            
        print("[Exotel WS] Connection closed")
        
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
                    print(f"[Exotel WS Cleanup] Released channel {released} for CallSid {call_sid}")
                    asyncio.create_task(dispatcher.dispatch())
            except Exception as release_err:
                print(f"[Exotel WS Cleanup Error]: {release_err}")
