from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from db.postgresql import fetch, fetchrow, execute

router = APIRouter()

class LeadCreate(BaseModel):
    lead_name: str
    phone_number: str
    status: Optional[str] = "New"
    interest: Optional[str] = "Premium Plot"
    user_id: str

class LeadUpdate(BaseModel):
    lead_name: Optional[str] = None
    phone_number: Optional[str] = None
    status: Optional[str] = None
    interest: Optional[str] = None

class LeadOut(BaseModel):
    lead_id: int
    lead_name: str
    phone_number: str
    status: str
    interest: str
    user_id: str
    created_at: datetime
    warning: Optional[str] = None

@router.get("/leads", response_model=List[LeadOut])
async def get_leads(user_id: str):
    """
    Fetches leads from the database for a specific user, sorted by creation date.
    """
    try:
        rows = await fetch("""
            SELECT lead_id, lead_name, phone_number, status, interest, user_id, created_at 
            FROM leads 
            WHERE user_id = $1 
            ORDER BY created_at DESC;
        """, user_id)
        
        return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch leads: {str(e)}"
        )

@router.post("/leads", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
async def create_lead(payload: LeadCreate):
    """
    Saves a new lead in the database.
    """
    try:
        row = await fetchrow("""
            INSERT INTO leads (lead_name, phone_number, status, interest, user_id)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING lead_id, lead_name, phone_number, status, interest, user_id, created_at;
        """, payload.lead_name, payload.phone_number, payload.status, payload.interest, payload.user_id)
        
        lead_dict = dict(row)
        
        # Schedule first call attempt (10 minutes delay)
        try:
            from datetime import datetime, timedelta
            from backgroundworker.celery_app import make_follow_up_call
            
            now = datetime.now()
            scheduled_time = now + timedelta(minutes=1)
            
            # Queue to Celery/RabbitMQ with a strict 60 seconds (1 minute) countdown
            make_follow_up_call.apply_async(
                args=[lead_dict["lead_id"], 1],
                countdown=60
            )
            
            # Record call schedule in database
            await execute("""
                INSERT INTO scheduled_calls (lead_id, attempt_number, scheduled_time, status)
                VALUES ($1, 1, $2, 'Pending');
            """, lead_dict["lead_id"], scheduled_time)
            
            # Update lead follow-up status
            await execute("""
                UPDATE leads 
                SET follow_up_status = 'Call 1 Scheduled' 
                WHERE lead_id = $1;
            """, lead_dict["lead_id"])
            
            print(f"[Leads API] Scheduled Call #1 for Lead {lead_dict['lead_id']} at {scheduled_time}")
        except Exception as queue_error:
            print(f"[Leads API] Warning: Failed to queue follow-up call task: {queue_error}")
            
        return lead_dict
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create lead: {str(e)}"
        )

@router.patch("/leads/{lead_id}", response_model=LeadOut)
async def update_lead(lead_id: int, payload: LeadUpdate):
    """
    Updates specific fields of a lead by ID.
    """
    try:
        existing = await fetchrow("SELECT * FROM leads WHERE lead_id = $1;", lead_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lead not found"
            )
            
        lead_name = payload.lead_name if payload.lead_name is not None else existing["lead_name"]
        phone_number = payload.phone_number if payload.phone_number is not None else existing["phone_number"]
        status_val = payload.status if payload.status is not None else existing["status"]
        interest = payload.interest if payload.interest is not None else existing["interest"]
        
        row = await fetchrow("""
            UPDATE leads 
            SET lead_name = $1, phone_number = $2, status = $3, interest = $4 
            WHERE lead_id = $5 
            RETURNING lead_id, lead_name, phone_number, status, interest, user_id, created_at;
        """, lead_name, phone_number, status_val, interest, lead_id)
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update lead: {str(e)}"
        )

@router.delete("/leads/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(lead_id: int):
    """
    Deletes a lead by ID.
    """
    try:
        # Fetch phone number to delete associated history
        lead = await fetchrow("SELECT phone_number FROM leads WHERE lead_id = $1;", lead_id)
        if lead and lead.get("phone_number"):
            phone = lead["phone_number"]
            # Extract last 10 digits to ensure match regardless of country code
            phone_suffix = ''.join(c for c in phone if c.isdigit())[-10:]
            
            # Delete all transcripts (conversations) for this number
            await execute("DELETE FROM conversations WHERE phone_number LIKE $1;", f"%{phone_suffix}%")
            
            # Delete all call logs for this number
            await execute("DELETE FROM calls WHERE to_phone_number LIKE $1;", f"%{phone_suffix}%")
            
        # Delete the lead (this will automatically CASCADE-delete scheduled_calls)
        await execute("DELETE FROM leads WHERE lead_id = $1;", lead_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete lead: {str(e)}"
        )
