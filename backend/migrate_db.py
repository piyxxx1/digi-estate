import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.postgresql import execute, fetch, close_pool

async def migrate():
    print("Starting database migration...")
    try:
        # 1. Migrate 'calls' table
        columns_calls = await fetch("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = 'calls';
        """)
        
        calls_column_names = {col['column_name'] for col in columns_calls}
        print(f"Existing columns in 'calls' table: {calls_column_names}")
        
        calls_migrations = []
        if 'to_phone_number' not in calls_column_names:
            calls_migrations.append("ALTER TABLE calls ADD COLUMN to_phone_number VARCHAR(50);")
        if 'direction' not in calls_column_names:
            calls_migrations.append("ALTER TABLE calls ADD COLUMN direction VARCHAR(20);")
        if 'flow_name' not in calls_column_names:
            calls_migrations.append("ALTER TABLE calls ADD COLUMN flow_name VARCHAR(100);")
        if 'outcome' not in calls_column_names:
            calls_migrations.append("ALTER TABLE calls ADD COLUMN outcome VARCHAR(250);")
        if 'call_sid' not in calls_column_names:
            calls_migrations.append("ALTER TABLE calls ADD COLUMN call_sid VARCHAR(100) UNIQUE;")
            
        if calls_migrations:
            for query in calls_migrations:
                print(f"Executing calls migration: {query}")
                await execute(query)
            print("Calls migration completed.")
        else:
            print("Calls table is up-to-date.")

        # 2. Migrate 'leads' table
        columns_leads = await fetch("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = 'leads';
        """)
        
        leads_column_names = {col['column_name'] for col in columns_leads}
        print(f"Existing columns in 'leads' table: {leads_column_names}")
        
        leads_migrations = []
        if 'status' not in leads_column_names:
            leads_migrations.append("ALTER TABLE leads ADD COLUMN status VARCHAR(50) DEFAULT 'New';")
        if 'interest' not in leads_column_names:
            leads_migrations.append("ALTER TABLE leads ADD COLUMN interest VARCHAR(100) DEFAULT 'Premium Plot';")
        if 'created_at' not in leads_column_names:
            leads_migrations.append("ALTER TABLE leads ADD COLUMN created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP;")
        if 'current_attempt' not in leads_column_names:
            leads_migrations.append("ALTER TABLE leads ADD COLUMN current_attempt INT DEFAULT 0;")
        if 'follow_up_status' not in leads_column_names:
            leads_migrations.append("ALTER TABLE leads ADD COLUMN follow_up_status VARCHAR(100) DEFAULT 'Pending First Call';")
            
        if leads_migrations:
            for query in leads_migrations:
                print(f"Executing leads migration: {query}")
                await execute(query)
            print("Leads migration completed.")
        else:
            print("Leads table is up-to-date.")

        # 3. Create and populate 'exophone_pool'
        print("Migrating 'exophone_pool' table...")
        await execute("""
            CREATE TABLE IF NOT EXISTS exophone_pool (
                phone_number VARCHAR(50) PRIMARY KEY,
                friendly_name VARCHAR(100),
                status VARCHAR(20) DEFAULT 'Available'
            );
        """)
        await execute("""
            INSERT INTO exophone_pool (phone_number, friendly_name)
            VALUES ('011-411-87680', '011-411-87680 (Delhi Office)'),
                   ('095-138-86363', '095-138-86363 (Support Number)')
            ON CONFLICT (phone_number) DO NOTHING;
        """)
        print("exophone_pool table migration completed.")

        # 4. Create 'conversations' table
        print("Migrating 'conversations' table...")
        await execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                conversation_id SERIAL PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                phone_number VARCHAR(50) NOT NULL,
                role VARCHAR(50) NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );
        """)
        print("conversations table migration completed.")

        # 5. Create 'scheduled_calls' table
        print("Migrating 'scheduled_calls' table...")
        await execute("""
            CREATE TABLE IF NOT EXISTS scheduled_calls (
                id SERIAL PRIMARY KEY,
                lead_id INT NOT NULL REFERENCES leads(lead_id) ON DELETE CASCADE,
                attempt_number INT NOT NULL,
                scheduled_time TIMESTAMP NOT NULL,
                status VARCHAR(20) DEFAULT 'Pending',
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("scheduled_calls table migration completed.")

    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        await close_pool()

if __name__ == "__main__":
    asyncio.run(migrate())
