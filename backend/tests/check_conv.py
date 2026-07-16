import asyncio
from db.postgresql import execute

async def main():
    await execute("UPDATE conversations SET phone_number = '08588091122' WHERE phone_number = '01141187680'")
    print("Fixed.")

if __name__ == "__main__":
    asyncio.run(main())
