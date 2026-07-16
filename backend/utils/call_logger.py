import asyncio
from db.postgresql import execute, fetchrow
from services.telephony.exotel_service import ExotelService

exotel = ExotelService()

async def lookup_caller_name(phone: str) -> str:
    if not phone:
        return "Unknown Lead"
    clean_phone = "".join(c for c in phone if c.isdigit())
    
    try:
        # Check database leads registry first
        query = "SELECT lead_name FROM leads WHERE phone_number LIKE $1 OR phone_number LIKE $2 LIMIT 1;"
        suffix = f"%{clean_phone[-10:]}" if len(clean_phone) >= 10 else f"%{clean_phone}"
        row = await fetchrow(query, f"%{clean_phone}", suffix)
        if row:
            return row["lead_name"]
    except Exception as e:
        print(f"[Call Logger] Error querying caller name from database: {e}")

    leads_map = {
        "+919823456789": "Rahul Sharma",
        "9823456789": "Rahul Sharma",
        "+918734567890": "Anita Desai",
        "8734567890": "Anita Desai",
        "+917645678901": "Vikram Malhotra",
        "7645678901": "Vikram Malhotra",
        "+919123456780": "Sneha Reddy",
        "9123456780": "Sneha Reddy",
        "+919876543210": "Test Client",
        "9876543210": "Test Client"
    }
    
    for k, v in leads_map.items():
        clean_k = "".join(c for c in k if c.isdigit())
        if clean_phone in clean_k or clean_k in clean_phone:
            return v
    return "Unknown Lead"

async def initialize_call_log(call_sid: str, stream_sid: str, direction: str = "incoming", from_num: str = None, to_num: str = None):
    """
    Initializes a call log in the database at the start of the call.
    """
    if not call_sid:
        return
    
    # Try fetching call details from Exotel API
    exotel_details = None
    if call_sid and call_sid != "mock":
        try:
            res = await exotel.get_call_details(call_sid)
            if res and "Call" in res:
                exotel_details = res["Call"]
        except Exception as e:
            print(f"[Call Logger] Error fetching call details from Exotel: {e}")
            
    # Extract fields from Exotel details, or fallback to arguments / defaults
    phone_number = from_num
    to_phone_number = to_num
    call_direction = direction
    outcome = "in-progress"
    
    if exotel_details:
        phone_number = exotel_details.get("From") or phone_number
        to_phone_number = exotel_details.get("To") or to_phone_number
        call_direction = exotel_details.get("Direction") or call_direction
        outcome = exotel_details.get("Status") or outcome
        
    caller_name = await lookup_caller_name(phone_number)
    
    print(f"[Call Logger] Initializing call: {call_sid} | {caller_name} | {phone_number} -> {to_phone_number} | Direction: {call_direction}")
    
    query = """
        INSERT INTO calls (caller_name, phone_number, to_phone_number, direction, flow_name, outcome, call_sid, transcript, ai_response, call_duration)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        ON CONFLICT (call_sid) DO UPDATE SET
            caller_name = COALESCE(EXCLUDED.caller_name, calls.caller_name),
            phone_number = COALESCE(EXCLUDED.phone_number, calls.phone_number),
            to_phone_number = COALESCE(EXCLUDED.to_phone_number, calls.to_phone_number),
            direction = COALESCE(EXCLUDED.direction, calls.direction),
            flow_name = COALESCE(EXCLUDED.flow_name, calls.flow_name),
            outcome = COALESCE(EXCLUDED.outcome, calls.outcome)
        RETURNING id;
    """
    try:
        await execute(query, caller_name, phone_number, to_phone_number, call_direction, "AI_FLOW", outcome, call_sid, "", "", 0)
    except Exception as e:
        print(f"[Call Logger] Error inserting initial call log: {e}")

async def finalize_call_log(call_sid: str, duration: int, history_messages: list):
    """
    Finalizes the call log in the database at the end of the call, updating transcript, ai_response, and duration.
    """
    if not call_sid:
        return
        
    # Format the transcript from history messages
    formatted_transcript = []
    last_assistant_msg = ""
    for msg in history_messages:
        role_label = "Priya" if msg.role == "assistant" else "Client"
        formatted_transcript.append(f"{role_label}: {msg.text}")
        if msg.role == "assistant":
            last_assistant_msg = msg.text
            
    transcript_text = " | ".join(formatted_transcript)
    ai_response = last_assistant_msg or "Voice conversation completed."
    
    # Try fetching call details from Exotel API to get final duration and status/outcome
    exotel_details = None
    if call_sid and call_sid != "mock":
        try:
            res = await exotel.get_call_details(call_sid)
            if res and "Call" in res:
                exotel_details = res["Call"]
        except Exception as e:
            print(f"[Call Logger] Error fetching final call details: {e}")
            
    outcome = "completed"
    if exotel_details:
        exotel_duration_str = exotel_details.get("Duration")
        if exotel_duration_str:
            try:
                duration = int(exotel_duration_str)
            except ValueError:
                pass
        
        status = exotel_details.get("Status")
        if status and status != "in-progress":
            outcome = status
            
async def handle_follow_up_retry(lead_id: int, current_attempt: int, call_sid: str, outcome: str):
    """
    Evaluates call outcome and schedules the next call attempt if appropriate.
    """
    try:
        from datetime import datetime
        from utils.scheduler_utils import calculate_next_working_time
        from backgroundworker.celery_app import make_follow_up_call
        
        # Fetch the latest status of the lead
        lead = await fetchrow("SELECT status, current_attempt FROM leads WHERE lead_id = $1;", lead_id)
        if not lead:
            return
            
        status = lead["status"]
        if status in ["Converted", "Accepted", "DNC"]:
            print(f"[Call Logger] Lead {lead_id} is in final status '{status}'. Stopping follow-up sequence.")
            await execute("UPDATE scheduled_calls SET status = 'Cancelled' WHERE lead_id = $1 AND status = 'Pending';", lead_id)
            return

        # Mark the current attempt as 'Completed'
        await execute("UPDATE scheduled_calls SET status = 'Completed' WHERE lead_id = $1 AND attempt_number = $2;", lead_id, current_attempt)
        
        # Schedule the next attempt if we haven't reached the limit of 3
        if current_attempt == 1:
            # Schedule Attempt #2 after 24 hours (1440 minutes)
            next_time, _ = calculate_next_working_time(datetime.now(), delay_minutes=1440)
            make_follow_up_call.apply_async(args=[lead_id, 2], eta=next_time)
            
            await execute("""
                INSERT INTO scheduled_calls (lead_id, attempt_number, scheduled_time, status)
                VALUES ($1, 2, $2, 'Pending');
            """, lead_id, next_time)
            
            await execute("""
                UPDATE leads 
                SET follow_up_status = 'Call 2 Scheduled' 
                WHERE lead_id = $1;
            """, lead_id)
            print(f"[Call Logger] Scheduled Call #2 for Lead {lead_id} at {next_time}")
            
        elif current_attempt == 2:
            # Schedule Attempt #3 after 48 hours (2880 minutes)
            next_time, _ = calculate_next_working_time(datetime.now(), delay_minutes=2880)
            make_follow_up_call.apply_async(args=[lead_id, 3], eta=next_time)
            
            await execute("""
                INSERT INTO scheduled_calls (lead_id, attempt_number, scheduled_time, status)
                VALUES ($1, 3, $2, 'Pending');
            """, lead_id, next_time)
            
            await execute("""
                UPDATE leads 
                SET follow_up_status = 'Call 3 Scheduled' 
                WHERE lead_id = $1;
            """, lead_id)
            print(f"[Call Logger] Scheduled Call #3 for Lead {lead_id} at {next_time}")
            
        elif current_attempt >= 3:
            # 3 attempts completed without conversion. Mark lead as Rejected.
            await execute("""
                UPDATE leads 
                SET status = 'Rejected', 
                    follow_up_status = 'Max Attempts Reached - Unreachable' 
                WHERE lead_id = $1;
            """, lead_id)
            print(f"[Call Logger] Max attempts reached for Lead {lead_id}. Lead marked as Rejected.")
            
    except Exception as e:
        print(f"[Call Logger] Error in handle_follow_up_retry: {e}")

async def finalize_call_log(call_sid: str, duration: int, history_messages: list):
    """
    Finalizes the call log in the database at the end of the call, updating transcript, ai_response, and duration.
    """
    if not call_sid:
        return
        
    # Format the transcript from history messages
    formatted_transcript = []
    last_assistant_msg = ""
    for msg in history_messages:
        role_label = "Priya" if msg.role == "assistant" else "Client"
        formatted_transcript.append(f"{role_label}: {msg.text}")
        if msg.role == "assistant":
            last_assistant_msg = msg.text
            
    transcript_text = " | ".join(formatted_transcript)
    ai_response = last_assistant_msg or "Voice conversation completed."
    
    # Try fetching call details from Exotel API to get final duration and status/outcome
    exotel_details = None
    if call_sid and call_sid != "mock":
        try:
            res = await exotel.get_call_details(call_sid)
            if res and "Call" in res:
                exotel_details = res["Call"]
        except Exception as e:
            print(f"[Call Logger] Error fetching final call details: {e}")
            
    outcome = "completed"
    if exotel_details:
        exotel_duration_str = exotel_details.get("Duration")
        if exotel_duration_str:
            try:
                duration = int(exotel_duration_str)
            except ValueError:
                pass
        
        status = exotel_details.get("Status")
        if status and status != "in-progress":
            outcome = status
            
    print(f"[Call Logger] Finalizing call: {call_sid} | Duration: {duration}s | Outcome: {outcome}")
    
    query = """
        UPDATE calls 
        SET transcript = $1, 
            ai_response = $2, 
            call_duration = $3, 
            outcome = $4
        WHERE call_sid = $5;
    """
    try:
        await execute(query, transcript_text, ai_response, duration, outcome, call_sid)
        
        # Check if the finalized call is an outbound follow-up attempt
        call_info = await fetchrow("SELECT phone_number, direction FROM calls WHERE call_sid = $1;", call_sid)
        if call_info and call_info["direction"] == "outbound":
            phone_number = call_info["phone_number"]
            clean_phone = "".join(c for c in phone_number if c.isdigit())
            suffix = f"%{clean_phone[-10:]}" if len(clean_phone) >= 10 else f"%{clean_phone}"
            
            lead = await fetchrow("SELECT lead_id, current_attempt, status FROM leads WHERE phone_number LIKE $1 OR phone_number LIKE $2 LIMIT 1;", f"%{clean_phone}", suffix)
            if lead:
                await handle_follow_up_retry(lead["lead_id"], lead["current_attempt"] or 0, call_sid, outcome)
                
    except Exception as e:
        print(f"[Call Logger] Error updating final call log and processing follow-up: {e}")
