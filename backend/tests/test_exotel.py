import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from services.telephony.exotel_service import ExotelService

async def main():
    service = ExotelService()
    res = await service.get_available_numbers()
    print("Numbers:", res)
    
if __name__ == "__main__":
    asyncio.run(main())
