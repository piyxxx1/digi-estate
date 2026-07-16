import asyncio
from dotenv import load_dotenv
load_dotenv('.env')
from services.telephony.exotel_service import ExotelService

async def test():
    s = ExotelService()
    res = await s.get_all_calls(limit=15)
    for c in res.get('calls', []):
        print(f"Sid: {c.get('Sid')}, Status: {c.get('Status')}, From: {c.get('From')}, To: {c.get('To')}, Direction: {c.get('Direction')}")

asyncio.run(test())
