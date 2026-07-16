import asyncio
from db.postgresql import execute

async def main():
    try:
        await execute("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS call_sid VARCHAR(255);")
        print("Column call_sid added to conversations.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
