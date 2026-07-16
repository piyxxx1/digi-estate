import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
from services.telephony.exotel_service import ExotelService

async def main():
    service = ExotelService()
    res = await service.get_call_details("24dcdfd384380ae16975aaae0b3d1a6q")
    print("Call 1:", res)
    res2 = await service.get_call_details("2356233a1637e294aed5a72100981a6q")
    print("Call 2:", res2)

if __name__ == "__main__":
    asyncio.run(main())
