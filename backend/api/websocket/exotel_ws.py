import json
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

import math
import struct

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
_greeting_chunks_cache: dict[int, list[str]] = {}
_greeting_cache_lock = asyncio.Lock()
_GREETING_TEXT = "नमस्ते, मैं ritu बोल रही हूँ, QUICK SPACE से। आज मैं आपकी कैसे मदद कर सकती हूँ?"

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

        print(f"[Greeting Cache] First call for {sample_rate}Hz — generating greeting...")
        audio_b64_raw = await tts_service.synthesize_realtime(_GREETING_TEXT, speech_sample_rate=sample_rate)
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

        # 200ms chunk sizes dynamically calculated per sample rate
        chunk_size = int(sample_rate * 2 * 0.20)  # 200ms
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

        chunk_size = int(sample_rate * 2 * 0.20)  # 200ms chunks
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
    # Exotel passes `sample-rate=24000` or `sample_rate=24000` as query params. Default is 8000
    param_rate = websocket.query_params.get("sample-rate") or websocket.query_params.get("sample_rate") or "8000"
    try:
        sample_rate = int(param_rate)
    except ValueError:
        sample_rate = 8000
    print(f"[Exotel WS] Call streaming configured at {sample_rate}Hz")

    # Start caching greeting eagerly on connect to reduce start latency
    asyncio.create_task(_ensure_greeting_cached(sample_rate))

    # Frame and Chunk parameters calculated dynamically
    frame_size_20ms = int(sample_rate * 2 * 0.02)  # Multiple check pad (20ms)
    chunk_size_200ms = int(sample_rate * 2 * 0.20)  # Playback chunk (200ms)

    stt_service = SarvamSTTService()
    tts_service = SarvamTTSService()
    audio_processor = AudioProcessor()
    ai_service = GeminiService()
    memory_manager = MemoryManager()
    
    stream_sid = None
    call_sid = None
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
    
    async def audio_generator():
        while True:
            chunk = await audio_queue.get()
            if chunk is None:
                break
            yield chunk

    async def send_greeting():
        nonlocal stream_sid, is_closed, greeting_playing
        
        if not stream_sid or is_closed:
            return

        print(f"[Exotel WS] Sending greeting to {stream_sid} at {sample_rate}Hz")
        try:
            # Dynamically ensure cached for target sample_rate
            await _ensure_greeting_cached(sample_rate)
            
            for chunk_b64 in _greeting_chunks_cache.get(sample_rate, []):
                if is_closed:
                    break
                payload = json.dumps({
                    "event": "media",
                    "stream_sid": stream_sid,
                    "media": {"payload": chunk_b64}
                }, separators=(',', ':'))
                await websocket.send_text(payload)
                # Dynamic pacing: sleep exactly as long as the chunk duration
                chunk_bytes = len(base64.b64decode(chunk_b64))
                duration = chunk_bytes / (sample_rate * 2)
                await asyncio.sleep(duration)

            greeting_playing = False
            print(f"[Exotel WS] Greeting complete, now listening")
            memory_manager.save_interaction(call_sid or "default_user", "assistant", _GREETING_TEXT)
        except asyncio.CancelledError:
            greeting_playing = False
            print("[Exotel WS] Greeting cancelled by barge-in")
            memory_manager.save_interaction(call_sid or "default_user", "assistant", "नमस्ते, मैं Priya बोल रही हूँ, Charaktaal Eco Village से...")
            raise
        except Exception as e:
            greeting_playing = False
            print(f"[Exotel WS] Greeting send error: {e}")

    async def send_clear():
        """Send clear event to Exotel to flush its audio buffer on barge-in."""
        nonlocal stream_sid, is_closed
        if not stream_sid or is_closed:
            return
        try:
            payload = json.dumps({
                "event": "clear",
                "stream_sid": stream_sid
            }, separators=(',', ':'))
            await websocket.send_text(payload)
            print("[Exotel WS] Clear sent to flush Exotel audio buffer")
        except Exception as e:
            print(f"[Exotel WS] Clear send error: {e}")

    async def handle_sarvam_responses():
        nonlocal stream_sid, latest_transcript, last_transcript_time, response_task, greeting_task, greeting_playing, bot_speaking, user_currently_speaking
        try:
            async for result in stt_service.stream_transcription(audio_generator()):
                msg_type = result.get("type", "")

                # VAD: User STARTED speaking → Log only, do not aggressively cancel yet
                if msg_type == "speech_start":
                    print("[Exotel WS] VAD Speech Start detected")
                    user_currently_speaking = True
                    continue

                # VAD: User STOPPED speaking → accelerate silence timer
                if msg_type == "speech_end":
                    print("[Exotel WS] VAD Speech End detected")
                    user_currently_speaking = False
                    last_transcript_time = asyncio.get_event_loop().time() - 0.2
                    continue

                # Transcript result
                transcript = ""
                if msg_type == "data":
                    transcript = result.get("data", {}).get("transcript", "")
                elif result.get("is_final") or msg_type == "transcript.final":
                    transcript = result.get("transcript", "")

                if transcript:
                    cleaned_t = transcript.strip().lower().replace(".", "").replace("?", "").replace("।", "")
                    ignore_list = ["हम्म", "क्या", "hmm", "han", "kya", "hello", "hi", "hey", "हाँ", "हा", "जी", "अच्छा", "हेलो"]

                    # FIX 3: If bot is currently speaking, ignore weak/short STT (echo from bot's own voice)
                    if bot_speaking:
                        if len(cleaned_t) < 12:
                            print(f"[Exotel WS] Ignoring STT while bot speaking (echo suppression): '{transcript}'")
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

                        # FIX 2: Perform barge-in cancellation + clear Exotel buffer
                        if greeting_playing and greeting_task and not greeting_task.done():
                            print("[Exotel WS] Transcript Barge-in: Cancelling greeting")
                            greeting_task.cancel()
                            greeting_playing = False
                            asyncio.create_task(send_clear())
                        if response_task and not response_task.done():
                            print("[Exotel WS] Transcript Barge-in: Cancelling AI response/TTS")
                            response_task.cancel()
                            asyncio.create_task(send_clear())
                    else:
                        print(f"[Exotel WS] Ignoring tiny/filler STT interruption: '{transcript}'")
                        # Accept it for standard processing only if AI is silent
                        if not greeting_playing and (response_task is None or response_task.done()):
                            if latest_transcript:
                                latest_transcript += " " + transcript
                            else:
                                latest_transcript = transcript
                            last_transcript_time = asyncio.get_event_loop().time()

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

    async def stream_pcm_to_exotel(pcm_bytes: bytes):
        """Send a chunk of raw PCM bytes to Exotel with dynamic real-time pacing."""
        nonlocal stream_sid, is_closed, bot_speaking
        if not stream_sid or is_closed or not pcm_bytes:
            return

        chunk_size_40ms = int(sample_rate * 2 * 0.04)  # 40ms chunk size
        for i in range(0, len(pcm_bytes), chunk_size_40ms):
            if is_closed:
                return
            chunk_data = pcm_bytes[i:i + chunk_size_40ms]
            # Pad to multiple of dynamic frame size
            if len(chunk_data) % frame_size_20ms != 0:
                pad = frame_size_20ms - (len(chunk_data) % frame_size_20ms)
                chunk_data = chunk_data + b'\x00' * pad

            payload = json.dumps({
                "event": "media",
                "stream_sid": stream_sid,
                "media": {
                    "payload": base64.b64encode(chunk_data).decode('utf-8')
                }
            }, separators=(',', ':'))
            await websocket.send_text(payload)
            
            # FIX 1: Dynamic real-time pacing — sleep exactly as long as the chunk duration
            duration = len(chunk_data) / (sample_rate * 2)
            await asyncio.sleep(duration)

    # Booking Script State Machine (Call Session Level)
    booking_step = None  # None, "ask_name", "ask_phone", "ask_visit_date"
    booking_details = {}

    async def run_ai_tts_pipeline(text: str):
        """Full streaming pipeline: text → Gemini stream → Sarvam TTS WS stream → Exotel PCM"""
        nonlocal stream_sid, is_closed, booking_step, booking_details, call_sid
        user_id = call_sid or "default_user"
        
        # Clean text for simple intent matching
        cleaned = text.strip().lower()
        cleaned_no_punct = cleaned.replace("।", "").replace(".", "").replace("?", "").replace("!", "").replace(",", "")
        words = cleaned_no_punct.split()
        
        # Check for cancel/negation intent during booking flow
        is_negation = False
        negations = ["nahi", "nahin", "no", "not", "नहीं", "ना", "नही", "cancel", "stop", "रद्द", "बंद"]
        for neg in negations:
            if neg in words:
                is_negation = True
                break

        # Check if the user is asking a question or requesting info instead of answering booking questions
        is_asking_info = False
        info_keywords = [
            "why", "what", "how", "when", "where", "who", "price", "rate", "cost", "info", "information", "details", "detail",
            "क्यों", "क्या", "कैसे", "कब", "कहाँ", "कौन", "प्राइस", "रेट", "कीमत", "जानकारी", "इंफॉर्मेशन", "डिटेल्स", "बताओ", "बताइए"
        ]
        for kw in info_keywords:
            if kw in words or (len(kw) > 3 and kw in cleaned_no_punct):
                is_asking_info = True
                break

        # State machine check
        use_scripted_fast_path = False
        fast_reply_text = ""
        
        # If user cancels, says no, or asks a question during booking flow, reset it
        if booking_step is not None and (is_negation or is_asking_info):
            print(f"[Booking Flow] User cancelled or asked a question at step {booking_step}. Resetting flow.")
            booking_step = None
            booking_details = {}
            # Proceed to standard Gemini route so it can reply naturally
            
        # Check for callback/busy intent
        is_callback_intent = False
        if booking_step is None and not is_negation:
            callback_keywords = [
                "talk later", "call later", "get back", "baad mein", "bad me", "call back", 
                "busy", "not right now", "बाद में", "बिज़ी", "व्यस्त", "बाद मे", "अभी नहीं", "abhi nahi"
            ]
            for kw in callback_keywords:
                if kw in cleaned:
                    is_callback_intent = True
                    break

        # Check for booking intent
        is_booking_intent = False
        if booking_step is None and not is_negation:
            # 1. Explicit booking keywords
            explicit_booking_words = ["book", "booking", "visit", "विज़िट", "बुक", "appointment", "अपॉइंटमेंट", "कन्फर्म", "confirm"]
            has_explicit_booking = False
            for pos in explicit_booking_words:
                if pos in words or (len(pos) > 3 and pos in cleaned_no_punct):
                    has_explicit_booking = True
                    break
            
            # 2. Affirmative/agreement keywords
            has_affirmation = False
            is_short_ji = ("जी" in words and len(words) <= 3)
            
            affirmative_words = [
                "haan", "han", "haanji", "hanji", "yes", "ok", "okay", "sure", "bilkul", 
                "theek", "हाँ", "हा", "हाँजी", "जी हाँ", "बिलकुल", "ठीक", "ज़रूर"
            ]
            for pos in affirmative_words:
                if pos in words or (len(pos) > 3 and pos in cleaned_no_punct):
                    has_affirmation = True
                    break
            
            if is_short_ji:
                has_affirmation = True

            # If user affirmed, check if assistant previously suggested booking a visit
            assistant_suggested_visit = False
            if has_affirmation:
                history = memory_manager.get_history(user_id)
                last_assistant_text = ""
                for msg in reversed(history):
                    if msg.role == "assistant":
                        last_assistant_text = msg.text.lower()
                        break
                
                if last_assistant_text:
                    suggest_keywords = ["visit", "book", "विज़िट", "बुक", "आना चाहेंगे", "चलना चाहेंगे", "apoint", "appointment", "अपॉइंटमेंट"]
                    if any(kw in last_assistant_text for kw in suggest_keywords):
                        assistant_suggested_visit = True

            if has_explicit_booking or (has_affirmation and assistant_suggested_visit):
                is_booking_intent = True

        if booking_step is None and is_callback_intent:
            fast_reply_text = "ठीक है, मैं आपको कब कॉल कर सकती हूँ?"
            use_scripted_fast_path = True
        elif booking_step is None and is_booking_intent:
            booking_step = "ask_name"
            fast_reply_text = "मैं आपके लिए site visit book कर देता हूँ। आपका पूरा नाम क्या है?"
            use_scripted_fast_path = True
        elif booking_step == "ask_name":
            booking_details["name"] = text
            booking_step = "ask_phone"
            fast_reply_text = "Thank you! आपका contact number क्या है?"
            use_scripted_fast_path = True
        elif booking_step == "ask_phone":
            booking_details["phone"] = text
            booking_step = "ask_visit_date"
            fast_reply_text = "आप किस date को visit करना चाहेंगे?"
            use_scripted_fast_path = True
        elif booking_step == "ask_visit_date":
            booking_details["date"] = text
            fast_reply_text = "तो मैं आपका visit confirm कर रहा हूँ। हमारी team एक दिन पहले details share करेगी। धन्यवाद!"
            booking_step = None  # Reset state machine
            use_scripted_fast_path = True

        pipeline_start_time = asyncio.get_event_loop().time()
        print(f"[Latency Profile] Starting response pipeline for: '{text[:40]}...'")

        # ── Fast Path Audio Playback (Bypasses Gemini & TTS Generation entirely!) ──
        if use_scripted_fast_path:
            print(f"[FAST PATH MATCH] State: '{booking_step}'. Reply: '{fast_reply_text}'")
            memory_manager.save_interaction(user_id, "user", text)
            
            # Check dynamic cache
            cached_chunks = _fast_path_cache.get(sample_rate, {}).get(fast_reply_text)
            if cached_chunks:
                print(f"[Fast Path Cache] Dynamic cache HIT! Instant streaming start.")
                for chunk_b64 in cached_chunks:
                    if is_closed:
                        break
                    payload = json.dumps({
                        "event": "media",
                        "stream_sid": stream_sid,
                        "media": {"payload": chunk_b64}
                    }, separators=(',', ':'))
                    await websocket.send_text(payload)
                    await asyncio.sleep(0.164)  # 200ms paced chunk
            else:
                # Persistent streaming fallback
                print("[Fast Path Cache] Cache MISS. Streaming from persistent WS connection...")
                async def text_gen():
                    yield fast_reply_text
                
                async for pcm_chunk in tts_service.stream_tts(
                    text_gen(),
                    language_code="hi-IN",
                    pace=1.0,
                    speech_sample_rate=sample_rate
                ):
                    await stream_pcm_to_exotel(pcm_chunk)
            
            await send_mark("response_complete")
            memory_manager.save_interaction(user_id, "assistant", fast_reply_text)
            
            total_duration = asyncio.get_event_loop().time() - pipeline_start_time
            print(f"[Latency Profile] [Fast Path] Turn Complete: {total_duration * 1000:.1f}ms")
            return

        # ── Standard Route: Gemini AI & Sarvam TTS Streaming ──
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
                buffer = ""
                async for chunk_text in ai_service.generate_response_stream(text, gemini_history):
                    if first_gemini_token_time is None:
                        first_gemini_token_time = asyncio.get_event_loop().time()
                        ttft = first_gemini_token_time - pipeline_start_time
                        print(f"[Latency Profile] TTFT (Time to First Gemini Token): {ttft * 1000:.1f}ms")
                    
                    full_response += chunk_text
                    buffer += chunk_text
                    
                    punctuation_marks = [',', '.', '?', '!', '।', '\n']
                    if any(p in buffer for p in punctuation_marks) or len(buffer.split()) >= 3:
                        yield buffer
                        buffer = ""
                
                if buffer.strip():
                    yield buffer

            # Pipe Gemini stream into Sarvam TTS
            bot_speaking = True  # FIX 3: Mark bot as speaking before audio begins
            async for pcm_chunk in tts_service.stream_tts(
                gemini_text_generator(),
                language_code="hi-IN",
                pace=1.0,
                speech_sample_rate=sample_rate
            ):
                if first_audio_chunk_time is None:
                    first_audio_chunk_time = asyncio.get_event_loop().time()
                    audio_latency = first_audio_chunk_time - pipeline_start_time
                    print(f"[Latency Profile] Audio Latency (Time to first TTS audio packet): {audio_latency * 1000:.1f}ms")
                    print(f"[Latency Profile] Total turn-around time (Silence → AI starts speaking): {audio_latency * 1000:.1f}ms")
                await stream_pcm_to_exotel(pcm_chunk)

            await send_mark("response_complete")
            memory_manager.save_interaction(user_id, "assistant", full_response)
            
            total_duration = asyncio.get_event_loop().time() - pipeline_start_time
            print(f"[Latency Profile] Complete turn execution time: {total_duration * 1000:.1f}ms")
            print(f"[Exotel WS] Streaming response complete: {full_response[:80]}...")

        except asyncio.CancelledError:
            print("[Exotel WS] run_ai_tts_pipeline cancelled (barge-in)")
            if full_response.strip():
                memory_manager.save_interaction(user_id, "assistant", full_response + "...")
            raise
        except Exception as e:
            print(f"[AI/TTS STREAM ERROR] {e}")

    async def process_after_silence():
        nonlocal latest_transcript, last_transcript_time, stream_sid, is_closed, response_task, user_currently_speaking
        
        last_interaction_time = asyncio.get_event_loop().time()
        
        while not is_closed:
            await asyncio.sleep(0.3)
            current_time = asyncio.get_event_loop().time()
            
            # Keep the interaction timer updated if anyone is speaking or system is processing
            if (bot_speaking or 
                greeting_playing or 
                user_currently_speaking or 
                bool(latest_transcript) or 
                (response_task and not response_task.done()) or
                (greeting_task and not greeting_task.done())):
                last_interaction_time = current_time

            if latest_transcript:
                silence_duration = current_time - last_transcript_time
                # Trigger response if:
                # 1. User stopped speaking and silence duration > 450ms
                # 2. Or fallback limit of 1.5s hit (in case of missing VAD speech_end packet)
                if (not user_currently_speaking and silence_duration > 0.45) or (silence_duration > 1.5):
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
            else:
                # Detect long silence when the line is completely idle
                if current_time - last_interaction_time > 10.0:
                    print("[Exotel WS] 11s silence detected. Prompting user.")
                    last_interaction_time = current_time + 5.0  # Prevent immediate re-trigger
                    
                    if response_task and not response_task.done():
                        response_task.cancel()
                        try:
                            await response_task
                        except asyncio.CancelledError:
                            pass
                            
                    silence_prompt = "[SYSTEM] The user has been completely silent for 11 seconds. Ask them if they are still there on the line in a short, natural way (e.g. 'Hello? Are you there?'), matching the language of the conversation."
                    response_task = asyncio.create_task(run_ai_tts_pipeline(silence_prompt))

    sarvam_task = asyncio.create_task(handle_sarvam_responses())
    silence_task = asyncio.create_task(process_after_silence())

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

                        # Establish persistent connection to Sarvam TTS immediately (Priority 1)
                        asyncio.create_task(tts_service.connect(sample_rate))
                        
                        # Pre-cache all scripted replies in background at this sample rate (Priority 4)
                        for reply in SCRIPTED_REPLIES:
                            asyncio.create_task(_ensure_fast_path_cached(reply, sample_rate))

                        greeting_playing = True
                        greeting_task = asyncio.create_task(send_greeting())
                    
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
                            bot_speaking = False  # FIX 3: Bot finished speaking

                    elif event == "clear":
                        print("[Exotel WS] Clear event: User interrupted (barge-in from Exotel)")
                        if greeting_playing and greeting_task and not greeting_task.done():
                            greeting_task.cancel()
                            greeting_playing = False
                        if response_task and not response_task.done():
                            response_task.cancel()
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
        await audio_queue.put(None)
        
        # Cleanly disconnect persistent TTS connection (Priority 1)
        await tts_service.disconnect()
        
        if greeting_task and not greeting_task.done():
            greeting_task.cancel()
        if not sarvam_task.done():
            sarvam_task.cancel()
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
