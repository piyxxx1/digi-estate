from dotenv import load_dotenv
load_dotenv(override=True)
import sys
import builtins

_original_print = builtins.print

def safe_print(*args, **kwargs):
    file = kwargs.get('file', sys.stdout)
    encoding = getattr(file, 'encoding', None) or 'utf-8'
    new_args = []
    for arg in args:
        if isinstance(arg, str):
            new_args.append(arg.encode(encoding, errors='replace').decode(encoding))
        else:
            new_args.append(arg)
    _original_print(*new_args, **kwargs)

builtins.print = safe_print
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.rest import health, crm
from api.websocket import exotel_ws
from contextlib import asynccontextmanager
import asyncio
from db.postgresql import get_pool, close_pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Eagerly pre-cache greeting audio on startup (matching telephony standard)
    from api.websocket.exotel_ws import _ensure_greeting_cached, _ensure_short_fillers_cached
    print("[Startup] Eagerly pre-caching greeting audio at 16000Hz...")
    asyncio.create_task(_ensure_greeting_cached(16000))
    asyncio.create_task(_ensure_short_fillers_cached(16000))
    
    # Eagerly initialize asyncpg pool
    print("[Startup] Initializing PostgreSQL connection pool...")
    try:
        await get_pool()
        print("[Startup] PostgreSQL connection pool initialized successfully.")
    except Exception as e:
        print(f"[Startup ERROR] Failed to initialize PostgreSQL pool: {e}")
        
    yield
    
    # Close pool on shutdown
    print("[Shutdown] Closing PostgreSQL connection pool...")
    await close_pool()

app = FastAPI(title="Ai-Caller Backend", lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(crm.router, prefix="/api", tags=["crm"])
app.include_router(exotel_ws.router, prefix="/ws", tags=["exotel"])
app.include_router(exotel_ws.router, tags=["exotel"])  # Supports direct /exotel path


@app.get("/")
async def root():
    return {"message": "Ai-Caller Backend is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
