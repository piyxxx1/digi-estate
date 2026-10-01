import os
import json
import asyncio
import re
import random
from typing import Dict, Any
from google import genai
from google.genai import types
from db.postgresql import execute, fetch, get_pool
from services.ai.property_prompts import PROPERTY_EXTRACTION_PROMPT
from utils.text_verification import verify_extracted_data
from models.property_models import UnitTypeItem

async def ingest_property(property_id: str, dealer_id: str, raw_text: str):
    """
    Background job to ingest property text, extract facts, verify them, and update status.
    Does not embed chunks yet.
    """
    try:
        # Mark as processing
        await execute("UPDATE properties SET status = 'processing' WHERE property_id = $1 AND dealer_id = $2", property_id, dealer_id)

        api_key = os.getenv("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        
        # Use flash for speed/cost as requested
        model_name = os.getenv("GEMINI_EXTRACTION_MODEL", "gemini-2.5-flash")

        config = types.GenerateContentConfig(
            system_instruction=PROPERTY_EXTRACTION_PROMPT,
            response_mime_type="text/plain",
            temperature=0.1
        )
        
        # Retry logic: retry once
        for attempt in range(2):
            try:
                response = await client.aio.models.generate_content(
                    model=model_name,
                    contents=[types.Content(role="user", parts=[types.Part(text=raw_text)])],
                    config=config
                )
                cleaned_text = response.text.strip()
                break
            except Exception as e:
                if attempt == 1:
                    raise e
                await asyncio.sleep(2)

        # Update DB with needs_review
        await execute(
            """
            UPDATE properties 
            SET cleaned_text = $1, extraction_warnings = '[]'::jsonb, status = 'needs_review', updated_at = NOW()
            WHERE property_id = $2 AND dealer_id = $3
            """,
            cleaned_text,
            property_id,
            dealer_id
        )

    except Exception as e:
        print(f"Error during property ingestion for {property_id}: {e}")
        await execute(
            "UPDATE properties SET status = 'failed', extraction_warnings = $1 WHERE property_id = $2 AND dealer_id = $3",
            json.dumps([f"Ingestion failed: {str(e)}"]),
            property_id,
            dealer_id
        )


async def embed_and_publish_property(property_id: str, dealer_id: str):
    """
    Called after dealer confirms facts. 
    Splits cleaned narrative into chunks, generates embeddings safely with rate-limiting,
    swaps chunks atomically, and sets status to 'live'.
    """
    try:
        # Fetch property to get cleaned_text
        rows = await fetch("SELECT cleaned_text FROM properties WHERE property_id = $1 AND dealer_id = $2", property_id, dealer_id)
        if not rows:
            return
            
        cleaned_text = rows[0]['cleaned_text']
        
        # Chunking by markdown heading (FIXED: single backslash for actual newline character)
        sections = re.split(r'(?m)^##\s+', cleaned_text)
        chunks = []
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
            
            lines = section.split('\n', 1)  # Fixed: split on actual newline '\n'
            if len(lines) > 1:
                topic = lines[0].strip().lower()
                content = section
            else:
                topic = "general"
                content = section
                
            chunks.append({"topic": topic, "content": content})
            
        api_key = os.getenv("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        
        # Control concurrency to avoid hitting 429 Rate Limits
        # Allows max 2 concurrent embedding requests at a time
        async def embed_single_with_retry(text: str, max_retries: int = 10):
            """Embeds a single chunk with exponential backoff for 429 errors."""
            delay = 3.0
            for attempt in range(max_retries):
                try:
                    res = await client.aio.models.embed_content(
                        model='text-embedding-004',
                        contents=text,
                        config=types.EmbedContentConfig(
                            task_type="RETRIEVAL_DOCUMENT",
                            output_dimensionality=768
                        )
                    )
                    return res.embeddings[0].values
                except Exception as e:
                    if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                        if attempt == max_retries - 1:
                            raise e
                        # Exponential backoff with jitter
                        sleep_time = delay * (2 ** attempt) + random.uniform(0.1, 1.0)
                        print(f"[429 Rate Limit] Retrying chunk embedding in {sleep_time:.2f}s...")
                        await asyncio.sleep(sleep_time)
                    else:
                        raise e

        # Get embeddings sequentially/controlled
        batch_texts = [c["content"] for c in chunks]
        embeddings = []
        
        if batch_texts:
            print(f"[Ingestion] Generating embeddings for {len(batch_texts)} chunks sequentially...")
            for t in batch_texts:
                # Hard limit pacing to guarantee we never trip the RPM/burst limit
                await asyncio.sleep(1.2)
                emb = await embed_single_with_retry(t)
                embeddings.append(emb)

        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Delete existing chunks for this property
                await conn.execute("DELETE FROM property_chunks WHERE property_id = $1", property_id)
                
                # Insert new chunks with vector casting
                for i, chunk in enumerate(chunks):
                    emb = embeddings[i] if i < len(embeddings) else None
                    if emb:
                        # Format as pgvector compatible string array
                        vector_str = f"[{','.join(map(str, emb))}]"
                        await conn.execute(
                            """
                            INSERT INTO property_chunks (property_id, dealer_id, topic, content, embedding)
                            VALUES ($1, $2, $3, $4, $5::vector)
                            """,
                            property_id, dealer_id, chunk["topic"], chunk["content"], vector_str
                        )
                
                # Set status to live
                await conn.execute(
                    "UPDATE properties SET status = 'live', updated_at = NOW() WHERE property_id = $1 AND dealer_id = $2",
                    property_id, dealer_id
                )
                
    except Exception as e:
        print(f"Error embedding property {property_id}: {e}")
        await execute("UPDATE properties SET status = 'failed' WHERE property_id = $1", property_id)