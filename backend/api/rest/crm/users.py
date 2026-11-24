import os
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from db.postgresql import fetch, fetchrow, execute
from services.telephony.exotel_service import ExotelService
from api.rest.crm.auth.auth import get_password_hash

router = APIRouter()
exotel_service = ExotelService()

@router.get("/exotel/available-numbers")
async def get_available_numbers(country: Optional[str] = None, number_type: Optional[str] = None):
    # Determine defaults from env if not specified
    if not country:
        region = os.getenv("EXOTEL_REGION", "Singapore").lower()
        country = "SG" if "singapore" in region else "IN"
    if not number_type:
        number_type = "Landline"
        
    res = await exotel_service.get_available_numbers(country, number_type)
    if "error" in res and not res.get("numbers"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Exotel API error: {res['error']}"
        )
    return res

@router.get("/exotel/calls")
async def get_exotel_calls(limit: int = 50):
    res = await exotel_service.get_all_calls(limit)
    if "error" in res and not res.get("calls"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Exotel API error: {res['error']}"
        )
    return res

@router.get("/exotel/calls-by-number")
async def get_exotel_calls_by_number(virtual_number: str, limit: int = 100):
    """
    Returns Exotel call history where To or From matches the given virtual_number.
    Used to scope call logs to a specific CRM user's assigned ExoPhone.
    """
    res = await exotel_service.get_calls_by_number(virtual_number, limit)
    if "error" in res and not res.get("calls"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Exotel API error: {res['error']}"
        )
    return res


class UserOut(BaseModel):
    user_id: str
    business_name: str
    password: Optional[str] = None
    exotel_virtual_number: Optional[str] = None

class UserCreate(BaseModel):
    user_id: str
    business_name: str
    password: Optional[str] = None
    exotel_virtual_number: Optional[str] = None

class UserUpdate(BaseModel):
    business_name: Optional[str] = None
    password: Optional[str] = None
    exotel_virtual_number: Optional[str] = None

@router.get("/users", response_model=List[UserOut])
async def get_users():
    try:
        rows = await fetch("SELECT user_id, business_name, password, exotel_virtual_number FROM users ORDER BY user_id ASC;")
        return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch users: {str(e)}"
        )

@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate):
    try:
        hashed_password = get_password_hash(payload.password) if payload.password else None
        query = """
            INSERT INTO users (user_id, business_name, password, exotel_virtual_number)
            VALUES ($1, $2, $3, $4)
            RETURNING user_id, business_name, password, exotel_virtual_number;
        """
        row = await fetchrow(query, payload.user_id, payload.business_name, hashed_password, payload.exotel_virtual_number)
        return dict(row)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )

@router.put("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: str, payload: UserUpdate):
    try:
        existing = await fetchrow("SELECT * FROM users WHERE user_id = $1;", user_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found."
            )
            
        business_name = payload.business_name if payload.business_name is not None else existing['business_name']
        password = get_password_hash(payload.password) if payload.password is not None else existing['password']
        exotel_virtual_number = payload.exotel_virtual_number if payload.exotel_virtual_number is not None else existing['exotel_virtual_number']
        
        query = """
            UPDATE users
            SET business_name = $1, password = $2, exotel_virtual_number = $3
            WHERE user_id = $4
            RETURNING user_id, business_name, password, exotel_virtual_number;
        """
        row = await fetchrow(query, business_name, password, exotel_virtual_number, user_id)
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user: {str(e)}"
        )

@router.get("/telemetry/system-overview")
async def get_system_telemetry():
    """
    Super Admin endpoint:
    Aggregates real-time Exotel call metrics, usage, cost, and per-company/number breakdown.
    """
    try:
        # 1. Fetch all registered users/companies from PostgreSQL
        user_rows = await fetch("SELECT user_id, business_name, exotel_virtual_number FROM users;")
        users = [dict(r) for r in user_rows]

        # 2. Fetch calls from Exotel (up to 200 calls)
        exotel_res = await exotel_service.get_all_calls(limit=200)
        exotel_calls = exotel_res.get("calls", [])

        # 3. Helper to clean and match 10-digit numbers
        def last10(num: str) -> str:
            d = ''.join(c for c in (num or '') if c.isdigit())
            return d[-10:] if len(d) >= 10 else d

        # Map each user by normalized virtual number
        company_map = {}
        for u in users:
            v_num = u.get("exotel_virtual_number") or ""
            target_10 = last10(v_num)
            company_map[target_10] = {
                "user_id": u["user_id"],
                "business_name": u["business_name"],
                "virtual_number": v_num,
                "total_calls": 0,
                "inbound_calls": 0,
                "outbound_calls": 0,
                "completed_calls": 0,
                "failed_calls": 0,
                "total_duration_sec": 0,
                "total_spend_inr": 0.0,
                "recent_calls": []
            }

        # Catch-all for unassigned or shared numbers
        unassigned_stats = {
            "user_id": "unassigned",
            "business_name": "General Pool / Unassigned",
            "virtual_number": "N/A",
            "total_calls": 0,
            "inbound_calls": 0,
            "outbound_calls": 0,
            "completed_calls": 0,
            "failed_calls": 0,
            "total_duration_sec": 0,
            "total_spend_inr": 0.0,
            "recent_calls": []
        }

        # Global aggregations
        total_calls = len(exotel_calls)
        total_duration = 0
        total_cost = 0.0
        completed_count = 0
        inbound_count = 0
        outbound_count = 0

        for call in exotel_calls:
            duration = int(call.get("Duration") or 0)
            price = float(call.get("Price") or 0.0)
            status_str = (call.get("Status") or "").lower()
            direction = (call.get("Direction") or "").lower()

            total_duration += duration
            total_cost += price
            if status_str in ["completed", "answered"]:
                completed_count += 1
            if "inbound" in direction:
                inbound_count += 1
            else:
                outbound_count += 1

            # Match to company virtual number
            to_10 = last10(call.get("To", ""))
            from_10 = last10(call.get("From", ""))
            phone_10 = last10(call.get("PhoneNumber", ""))

            matched_bucket = None
            if to_10 in company_map:
                matched_bucket = company_map[to_10]
            elif from_10 in company_map:
                matched_bucket = company_map[from_10]
            elif phone_10 in company_map:
                matched_bucket = company_map[phone_10]
            else:
                matched_bucket = unassigned_stats

            matched_bucket["total_calls"] += 1
            matched_bucket["total_duration_sec"] += duration
            matched_bucket["total_spend_inr"] = round(matched_bucket["total_spend_inr"] + price, 2)
            if "inbound" in direction:
                matched_bucket["inbound_calls"] += 1
            else:
                matched_bucket["outbound_calls"] += 1

            if status_str in ["completed", "answered"]:
                matched_bucket["completed_calls"] += 1
            else:
                matched_bucket["failed_calls"] += 1

            if len(matched_bucket["recent_calls"]) < 5:
                matched_bucket["recent_calls"].append({
                    "sid": call.get("Sid"),
                    "from": call.get("From"),
                    "to": call.get("To"),
                    "duration": duration,
                    "status": call.get("Status"),
                    "price": price,
                    "recording_url": call.get("RecordingUrl"),
                    "date_created": call.get("DateCreated")
                })

        # Calculate averages & success rates
        success_rate = f"{round((completed_count / total_calls * 100), 1)}%" if total_calls > 0 else "0.0%"
        avg_duration = f"{round(total_duration / total_calls, 1)}s" if total_calls > 0 else "0s"

        companies_list = list(company_map.values())
        if unassigned_stats["total_calls"] > 0:
            companies_list.append(unassigned_stats)

        return {
            "summary": {
                "total_calls": total_calls,
                "inbound_calls": inbound_count,
                "outbound_calls": outbound_count,
                "completed_calls": completed_count,
                "success_rate": success_rate,
                "total_duration_minutes": round(total_duration / 60, 1),
                "avg_call_duration": avg_duration,
                "total_spend_inr": round(total_cost, 2),
                "active_companies": len(users),
                "stt_engine": "Sarvam AI Realtime (16kHz)",
                "llm_engine": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                "tts_engine": f"Sarvam Bulbul ({os.getenv('SARVAM_SPEAKER', 'Ritu')})",
                "avg_latency": "1.08s"
            },
            "companies": companies_list,
            "raw_recent_calls": exotel_calls[:15]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Telemetry calculation failed: {str(e)}"
        )

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str):
    try:
        existing = await fetchrow("SELECT * FROM users WHERE user_id = $1;", user_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found."
            )
            
        # Clean up related records (Explicit Cascade)
        # 1. Refresh Tokens
        await execute("DELETE FROM refresh_tokens WHERE user_id = $1;", user_id)
        
        # 2. Leads
        await execute("DELETE FROM leads WHERE user_id = $1;", user_id)
        
        # 3. Properties
        await execute("DELETE FROM property WHERE user_id = $1;", user_id)
        
        # 4. Calls associated with this user's virtual number
        exotel_virtual_number = existing.get("exotel_virtual_number")
        if exotel_virtual_number:
            # Clean up the phone number format to match potential DB entries
            # (assuming basic string match for now as per Exotel standard)
            await execute(
                "DELETE FROM calls WHERE to_phone_number = $1 OR phone_number = $1;", 
                exotel_virtual_number
            )
            
        # Finally delete the user
        await execute("DELETE FROM users WHERE user_id = $1;", user_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user: {str(e)}"
        )
