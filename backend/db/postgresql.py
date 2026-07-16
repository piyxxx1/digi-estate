import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ai_caller_db")

# Global connection pool instance
_pool = None

async def get_pool() -> asyncpg.Pool:
    """
    Returns the global connection pool. Initializes it if it does not exist.
    """
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            min_size=2,
            max_size=15,
            max_inactive_connection_lifetime=300.0
        )
    return _pool

async def close_pool():
    """
    Closes the global database pool on shutdown.
    """
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None

async def execute(query: str, *args) -> str:
    """
    Executes a write query (e.g., INSERT, UPDATE, DELETE) and returns the status.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)

async def fetch(query: str, *args) -> list:
    """
    Fetches records for an SQL select query and returns list of Record objects.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)

async def fetchrow(query: str, *args) -> asyncpg.Record:
    """
    Fetches a single row record for an SQL query or None.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)

async def fetchval(query: str, *args):
    """
    Fetches a single value (e.g., aggregate sums/counts) or None.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)
