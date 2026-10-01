import os
import asyncio
from google import genai
from google.genai import types
import json

PROPERTY_EXTRACTION_PROMPT = \"\"\"
You are a real estate data extraction assistant. Your task is to process the raw text provided about a property and extract the information into a structured JSON format.

INSTRUCTIONS:
1. Extract all unit types available in the property. A unit type should include type, config, prices, and areas if mentioned.
   - Prices must be extracted as numeric values in rupees. Do NOT use strings for prices.
   - Ensure you distinguish between total price (price_min, price_max) and price per square yard/foot.
   - If a price is clearly marked as a starting price or reference point, set price_is_reference to true.
2. Extract all other relevant facts into a free-form facts object. This should include things like possession timeline, connection charges, rebate, RERA position, payment plan, etc.
3. Organize the remaining descriptive information into a cleaned_text string. Use clear markdown headings for topics.
4. Output NULL for anything not present in the text. NEVER guess or hallucinate values.
\"\"\"

async def test():
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "unit_types": types.Schema(
                type=types.Type.ARRAY,
                items=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "type": types.Schema(type=types.Type.STRING),
                        "config": types.Schema(type=types.Type.STRING),
                        "price_is_reference": types.Schema(type=types.Type.BOOLEAN)
                    },
                    required=["type", "config", "price_is_reference"]
                )
            ),
            "facts": types.Schema(type=types.Type.OBJECT, description="Free-form facts"),
            "cleaned_text": types.Schema(type=types.Type.STRING)
        },
        required=["unit_types", "facts", "cleaned_text"]
    )
    
    config = types.GenerateContentConfig(
        system_instruction=PROPERTY_EXTRACTION_PROMPT,
        response_mime_type="application/json",
        response_schema=schema,
        temperature=0.1
    )
    
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=[types.Content(role="user", parts=[types.Part(text="2 BHK flat in Noida, 75L starting price, possession by Dec 2026.")])],
        config=config
    )
    print(response.text)

asyncio.run(test())
