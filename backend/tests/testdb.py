import sys
import os
import asyncio

# Ensure the backend directory is in the path for proper import resolution
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.postgresql import execute, fetch, fetchrow, fetchval, close_pool

async def main():
    print("--------------------------------------------------")
    print("Testing PostgreSQL Connection using asyncpg...")
    print("--------------------------------------------------")
    try:
        # 1. Fetch the server version to check active connection
        version = await fetchrow("SELECT version();")
        print("[OK] Connected successfully!")
        print(f"Server Version: {version[0]}\n")

        # 2. Check if the 'calls' table exists
        table_check = await fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'calls'
            );
        """)
        
        if table_check:
            print("[INFO] Table 'calls' exists in public schema.")
        else:
            print("[INFO] Table 'calls' does not exist. Creating table structure...")
            await execute("""
                CREATE TABLE IF NOT EXISTS calls (
                    id SERIAL PRIMARY KEY,
                    caller_name VARCHAR(100),
                    phone_number VARCHAR(20),
                    transcript TEXT,
                    ai_response TEXT,
                    call_duration INT,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            print("[OK] Table 'calls' created successfully.")

        # 3. Insert a mock call record to test write queries
        print("\nInserting a mock call record...")
        insert_query = """
            INSERT INTO calls (caller_name, phone_number, transcript, ai_response, call_duration)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, created_at;
        """
        new_row = await fetchrow(
            insert_query, 
            "Test Client", 
            "+91 98765 43210", 
            "Namaste Priya, I want to check details about peak block cottages.", 
            "Namaste! The peak block features pristine Himalayan views and 3 BHK layouts.", 
            35
        )
        print(f"[OK] Row inserted! ID: {new_row['id']} | Created At: {new_row['created_at']}")

        # 4. Fetch the last 5 records to test read queries
        print("\nFetching latest call records:")
        records = await fetch("SELECT id, caller_name, phone_number, call_duration, created_at FROM calls ORDER BY created_at DESC LIMIT 5;")
        for record in records:
            print(f" - ID: {record['id']} | Name: {record['caller_name']} | Phone: {record['phone_number']} | Duration: {record['call_duration']}s | Created: {record['created_at']}")

    except Exception as e:
        print(f"\n[ERROR] Database connection or query failed: {e}")
        print("Please check your DATABASE_URL environment setting in backend/.env")
    finally:
        # 5. Clean up by closing connection pool
        print("\nClosing connection pool...")
        await close_pool()
        print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
