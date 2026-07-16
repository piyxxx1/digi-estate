from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from db.postgresql import fetch, fetchrow

router = APIRouter()

# --- Pydantic Schema Definitions ---
class CallCreate(BaseModel):
    caller_name: Optional[str] = None
    phone_number: Optional[str] = None
    transcript: Optional[str] = None
    ai_response: Optional[str] = None
    call_duration: Optional[int] = None
    to_phone_number: Optional[str] = None
    direction: Optional[str] = None
    flow_name: Optional[str] = None
    outcome: Optional[str] = None
    call_sid: Optional[str] = None

class CallOut(BaseModel):
    id: int
    caller_name: Optional[str] = None
    phone_number: Optional[str] = None
    transcript: Optional[str] = None
    ai_response: Optional[str] = None
    call_duration: Optional[int] = None
    to_phone_number: Optional[str] = None
    direction: Optional[str] = None
    flow_name: Optional[str] = None
    outcome: Optional[str] = None
    call_sid: Optional[str] = None
    created_at: datetime

# --- Endpoints ---

@router.get("/calls", response_model=List[CallOut])
async def get_calls(user_id: str):
    """
    Fetches call history logs from the database, joined with leads to resolve names
    and filtered by user_id to only return calls corresponding to registered leads.
    """
    try:
        rows = await fetch("""
            SELECT c.id, 
                   l.lead_name AS caller_name, 
                   c.phone_number, 
                   c.transcript, 
                   c.ai_response, 
                   c.call_duration, 
                   c.to_phone_number, 
                   c.direction, 
                   c.flow_name, 
                   c.outcome, 
                   c.call_sid, 
                   c.created_at 
            FROM calls c
            INNER JOIN leads l ON (
                CASE 
                    WHEN LENGTH(REGEXP_REPLACE(c.phone_number, '[^0-9]', '', 'g')) >= 10 
                         AND LENGTH(REGEXP_REPLACE(l.phone_number, '[^0-9]', '', 'g')) >= 10
                    THEN RIGHT(REGEXP_REPLACE(c.phone_number, '[^0-9]', '', 'g'), 10) = RIGHT(REGEXP_REPLACE(l.phone_number, '[^0-9]', '', 'g'), 10)
                    ELSE REGEXP_REPLACE(c.phone_number, '[^0-9]', '', 'g') = REGEXP_REPLACE(l.phone_number, '[^0-9]', '', 'g')
                END
            )
            WHERE l.user_id = $1
            ORDER BY c.created_at DESC;
        """, user_id)
        return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch calls history: {str(e)}"
        )

@router.post("/calls", response_model=CallOut, status_code=status.HTTP_201_CREATED)
async def create_call(payload: CallCreate):
    """
    Saves or updates a call log record in the database.
    """
    try:
        query = """
            INSERT INTO calls (caller_name, phone_number, transcript, ai_response, call_duration, 
                               to_phone_number, direction, flow_name, outcome, call_sid)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (call_sid) DO UPDATE SET
                caller_name = COALESCE(EXCLUDED.caller_name, calls.caller_name),
                phone_number = COALESCE(EXCLUDED.phone_number, calls.phone_number),
                transcript = COALESCE(EXCLUDED.transcript, calls.transcript),
                ai_response = COALESCE(EXCLUDED.ai_response, calls.ai_response),
                call_duration = COALESCE(EXCLUDED.call_duration, calls.call_duration),
                to_phone_number = COALESCE(EXCLUDED.to_phone_number, calls.to_phone_number),
                direction = COALESCE(EXCLUDED.direction, calls.direction),
                flow_name = COALESCE(EXCLUDED.flow_name, calls.flow_name),
                outcome = COALESCE(EXCLUDED.outcome, calls.outcome)
            RETURNING id, caller_name, phone_number, transcript, ai_response, call_duration, 
                      to_phone_number, direction, flow_name, outcome, call_sid, created_at;
        """
        row = await fetchrow(
            query,
            payload.caller_name,
            payload.phone_number,
            payload.transcript,
            payload.ai_response,
            payload.call_duration,
            payload.to_phone_number,
            payload.direction,
            payload.flow_name,
            payload.outcome,
            payload.call_sid
        )
        return dict(row)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create/update call log: {str(e)}"
        )

class OutboundCallRequest(BaseModel):
    user_id: str
    lead_phone: str

@router.post("/calls/outbound-ai", status_code=status.HTTP_200_OK)
async def initiate_outbound_ai_call(payload: OutboundCallRequest):
    """
    Initiates an outbound call to a lead from the user's assigned ExoPhone,
    connecting the lead directly to the AI Flow (Exotel App).
    """
    try:
        from services.telephony.exotel_service import ExotelService
        exotel_service = ExotelService()
        
        # 1. Fetch user's assigned ExoPhone
        user_row = await fetchrow("SELECT exotel_virtual_number FROM users WHERE user_id = $1", payload.user_id)
        if not user_row or not user_row.get("exotel_virtual_number"):
            raise HTTPException(status_code=400, detail="User does not have an assigned virtual number.")
        exophone = user_row["exotel_virtual_number"]
        
        # 2. Get the Voice URL for this ExoPhone from Exotel
        nums_res = await exotel_service.get_available_numbers()
        app_url = None
        if nums_res and "numbers" in nums_res:
            def last10(n):
                d = "".join(c for c in (n or "") if c.isdigit())
                return d[-10:] if len(d) >= 10 else d
            
            target = last10(exophone)
            for num in nums_res["numbers"]:
                if last10(num.get("phone_number")) == target:
                    app_url = num.get("voice_url")
                    break
        
        if not app_url:
            raise HTTPException(status_code=400, detail="Could not find the Exotel App URL for the assigned virtual number.")
            
        # Format the lead_phone to ensure Exotel accepts it (e.g., prefix 0 for 10-digit Indian numbers)
        formatted_phone = "".join(c for c in payload.lead_phone if c.isdigit() or c == '+')
        if len(formatted_phone) == 10 and not formatted_phone.startswith('+') and not formatted_phone.startswith('0'):
            formatted_phone = '0' + formatted_phone
        elif len(formatted_phone) == 12 and formatted_phone.startswith('91'):
            formatted_phone = '+' + formatted_phone

        # 3. Make the Outbound Call connecting to the App URL
        call_res = await exotel_service.make_outbound_ai_call(formatted_phone, exophone, app_url)
        
        if "error" in call_res:
            raise HTTPException(status_code=502, detail=f"Exotel API error: {call_res['error']}")
            
        return {"message": "Outbound call initiated successfully.", "details": call_res}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate outbound AI call: {str(e)}"
        )

@router.get("/calls/live-transcript/{call_sid}")
async def get_live_transcript(call_sid: str):
    """
    Fetches the live transcript (conversation history) from Redis memory manager for a given active call.
    Also returns the call status from the database.
    """
    try:
        from services.ai.memory_manager import MemoryManager
        from db.postgresql import fetchrow
        
        memory_manager = MemoryManager()
        history = memory_manager.get_history(call_sid, limit=50)
        messages = [{"role": msg.role, "text": msg.text} for msg in history]
        
        row = await fetchrow("SELECT outcome FROM calls WHERE call_sid = $1", call_sid)
        call_status = row["outcome"] if row else "in-progress"
        
        return {"messages": messages, "status": call_status}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch live transcript: {str(e)}"
        )

@router.get("/calls/history/{lead_phone}")
async def get_call_history(lead_phone: str):
    """
    Fetches the full conversation history from PostgreSQL for a specific lead.
    """
    try:
        from db.postgresql import fetch
        clean_phone = "".join(c for c in lead_phone if c.isdigit())
        suffix = f"%{clean_phone[-10:]}" if len(clean_phone) >= 10 else f"%{clean_phone}"
        
        rows = await fetch("""
            SELECT cv.role, cv.message, cv.created_at, cv.call_sid, c.call_duration
            FROM conversations cv
            LEFT JOIN calls c ON cv.call_sid = c.call_sid
            WHERE cv.phone_number LIKE $1 OR cv.phone_number LIKE $2
            ORDER BY cv.created_at ASC;
        """, f"%{clean_phone}", suffix)
        
        messages = [{
            "role": row["role"], 
            "text": row["message"], 
            "time": row["created_at"].strftime("%I:%M %p"),
            "date": row["created_at"].strftime("%d %b %Y"),
            "timestamp": row["created_at"].isoformat(),
            "call_sid": row.get("call_sid"),
            "call_duration": row.get("call_duration")
        } for row in rows]
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversation history: {str(e)}"
        )
