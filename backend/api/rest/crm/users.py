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
