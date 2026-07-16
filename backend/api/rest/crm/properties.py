from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from db.postgresql import fetch, fetchrow, execute
from typing import List, Optional

router = APIRouter()

# --- Pydantic Schema Definitions ---
class PropertyCreate(BaseModel):
    property_heading: str
    description: str = Field(..., alias="property_details")
    user_id: str

    class Config:
        populate_by_name = True

class PropertyOut(BaseModel):
    id: int
    property_heading: Optional[str] = None
    property_details: str
    user_id: Optional[str] = None

# --- Endpoints ---

@router.get("/properties", response_model=List[PropertyOut])
async def get_properties(user_id: Optional[str] = None):
    """
    Fetches listed properties, optionally filtering by user_id.
    """
    try:
        if user_id is not None:
            rows = await fetch("SELECT id, property_heading, property_details, user_id FROM property WHERE user_id = $1 OR user_id IS NULL ORDER BY id ASC;", user_id)
        else:
            rows = await fetch("SELECT id, property_heading, property_details, user_id FROM property ORDER BY id ASC;")
        return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch properties: {str(e)}"
        )

@router.post("/properties", response_model=PropertyOut, status_code=status.HTTP_201_CREATED)
async def create_property(payload: PropertyCreate):
    """
    Inserts a new property associated with a user into the database.
    """
    try:
        query = "INSERT INTO property (property_heading, property_details, user_id) VALUES ($1, $2, $3) RETURNING id, property_heading, property_details, user_id;"
        row = await fetchrow(query, payload.property_heading, payload.description, payload.user_id)
        return dict(row)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save property: {str(e)}"
        )

@router.delete("/properties/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(property_id: int):
    """
    Removes a property listing from the database by ID.
    """
    try:
        exists = await fetchrow("SELECT id FROM property WHERE id = $1;", property_id)
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Property with ID {property_id} not found."
            )
        await execute("DELETE FROM property WHERE id = $1;", property_id)
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete property: {str(e)}"
        )

@router.put("/properties/{property_id}", response_model=PropertyOut)
async def update_property(property_id: int, payload: PropertyCreate):
    """
    Updates an existing property's details and user association.
    """
    try:
        exists = await fetchrow("SELECT id FROM property WHERE id = $1;", property_id)
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Property with ID {property_id} not found."
            )
        query = "UPDATE property SET property_heading = $1, property_details = $2, user_id = $3 WHERE id = $4 RETURNING id, property_heading, property_details, user_id;"
        row = await fetchrow(query, payload.property_heading, payload.description, payload.user_id, property_id)
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update property: {str(e)}"
        )
