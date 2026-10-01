from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from typing import List, Optional
from uuid import UUID
import json
from datetime import datetime

from db.postgresql import fetch, fetchrow, execute
from models.property_models import PropertyCreateRequest, PropertyUpdateRequest, PropertyOut, PropertyReviewConfirmRequest
from api.rest.crm.auth.auth import get_current_user
from services.property_ingestion import ingest_property, embed_and_publish_property

router = APIRouter()

def parse_property_row(row: dict) -> dict:
    row = dict(row)
    if isinstance(row.get('unit_types'), str):
        row['unit_types'] = json.loads(row['unit_types'])
    if isinstance(row.get('facts'), str):
        row['facts'] = json.loads(row['facts'])
    if isinstance(row.get('extraction_warnings'), str):
        row['extraction_warnings'] = json.loads(row['extraction_warnings'])
    return row

@router.get("/properties", response_model=List[PropertyOut])
async def list_properties(current_user: dict = Depends(get_current_user)):
    dealer_id = UUID(str(current_user['dealer_id']))
    try:
        rows = await fetch("SELECT * FROM properties WHERE dealer_id = $1 ORDER BY created_at DESC;", dealer_id)
        return [parse_property_row(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/properties", response_model=PropertyOut, status_code=status.HTTP_201_CREATED)
async def create_property(
    payload: PropertyCreateRequest, 
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    dealer_id = UUID(str(current_user['dealer_id']))
    prop_status = 'processing' if payload.raw_text else 'draft'
    try:
        row = await fetchrow(
            """
            INSERT INTO properties (dealer_id, name, aliases, city, region, property_type, unit_types, facts, raw_text, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *;
            """,
            dealer_id,
            payload.name,
            payload.aliases,
            payload.city,
            payload.region,
            payload.property_type,
            json.dumps([u.model_dump() for u in payload.unit_types]),
            json.dumps(payload.facts),
            payload.raw_text,
            prop_status
        )
        
        prop_id = str(row['property_id'])
        if payload.raw_text:
            background_tasks.add_task(ingest_property, prop_id, str(dealer_id), payload.raw_text)
            
        return parse_property_row(row)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/properties/{property_id}", response_model=PropertyOut)
async def get_property(property_id: UUID, current_user: dict = Depends(get_current_user)):
    dealer_id = UUID(str(current_user['dealer_id']))
    row = await fetchrow("SELECT * FROM properties WHERE property_id = $1 AND dealer_id = $2;", property_id, dealer_id)
    if not row:
        raise HTTPException(status_code=404, detail="Property not found")
    return parse_property_row(row)

@router.put("/properties/{property_id}", response_model=PropertyOut)
async def update_property(
    property_id: UUID, 
    payload: PropertyUpdateRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    dealer_id = UUID(str(current_user['dealer_id']))
    existing = await fetchrow("SELECT * FROM properties WHERE property_id = $1 AND dealer_id = $2;", property_id, dealer_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Property not found")
        
    updates = []
    values = []
    idx = 1
    
    trigger_ingestion = False
    payload_dict = payload.model_dump(exclude_unset=True)
    
    # Trigger ingestion if raw_text changed, or if it failed previously
    if 'raw_text' in payload_dict:
        if payload_dict['raw_text'] != existing['raw_text'] or existing['status'] == 'failed':
            trigger_ingestion = True
            payload_dict['status'] = 'reindexing' if existing['status'] != 'failed' else 'processing'
        
    for k, v in payload_dict.items():
        if k in ['unit_types', 'facts']:
            v = json.dumps([i.model_dump() if hasattr(i, 'model_dump') else i for i in v]) if k == 'unit_types' else json.dumps(v)
        updates.append(f"{k} = ${idx}")
        values.append(v)
        idx += 1
        
    updates.append(f"updated_at = NOW()")
    values.append(property_id)
    values.append(dealer_id)
    
    query = f"UPDATE properties SET {', '.join(updates)} WHERE property_id = ${idx} AND dealer_id = ${idx+1} RETURNING *;"
    
    try:
        updated_row = await fetchrow(query, *values)
        if trigger_ingestion and updated_row['raw_text']:
            background_tasks.add_task(ingest_property, str(property_id), str(dealer_id), updated_row['raw_text'])
        return parse_property_row(updated_row)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/properties/{property_id}/confirm", response_model=PropertyOut)
async def confirm_property(
    property_id: UUID, 
    payload: PropertyReviewConfirmRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    dealer_id = UUID(str(current_user['dealer_id']))
    existing = await fetchrow("SELECT * FROM properties WHERE property_id = $1 AND dealer_id = $2;", property_id, dealer_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Property not found")
        
    # Update facts/unit_types first, clear warnings, keep status needs_review until chunks are ready
    try:
        updated_row = await fetchrow(
            """
            UPDATE properties 
            SET unit_types = $1, facts = $2, extraction_warnings = '[]'::jsonb
            WHERE property_id = $3 AND dealer_id = $4
            RETURNING *;
            """,
            json.dumps([u.model_dump() for u in payload.unit_types]),
            json.dumps(payload.facts),
            property_id,
            dealer_id
        )
        # trigger embed
        background_tasks.add_task(embed_and_publish_property, str(property_id), str(dealer_id))
        return parse_property_row(updated_row)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/properties/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(property_id: UUID, current_user: dict = Depends(get_current_user)):
    dealer_id = UUID(str(current_user['dealer_id']))
    existing = await fetchrow("SELECT property_id FROM properties WHERE property_id = $1 AND dealer_id = $2;", property_id, dealer_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Property not found")
        
    try:
        await execute("DELETE FROM properties WHERE property_id = $1 AND dealer_id = $2;", property_id, dealer_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
