import asyncio, sys
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from db.postgresql import execute, fetch, close_pool

async def main():
    # Alter leads table (property was already VARCHAR)
    await execute("ALTER TABLE leads ALTER COLUMN user_id TYPE VARCHAR(255);")
    
    # Verify all
    rows = await fetch("""
        SELECT table_name, column_name, data_type 
        FROM information_schema.columns 
        WHERE column_name = 'user_id' AND table_name IN ('users', 'property', 'leads')
        ORDER BY table_name;
    """)
    for r in rows:
        print(f"{r['table_name']}.user_id = {r['data_type']}")

    await close_pool()

asyncio.run(main())
