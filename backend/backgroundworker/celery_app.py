import os
import sys
import asyncio
from celery import Celery
from datetime import datetime

# Add the parent directory to sys.path to resolve imports when running as a worker
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.postgresql import fetchrow, execute
from services.telephony.exotel_service import ExotelService

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672//")

celery_app = Celery(
    "tasks",
    broker=RABBITMQ_URL,
    backend="rpc://"
)

# Configure Celery settings for timezone and execution stability
celery_app.conf.update(
    timezone='Asia/Kolkata',
    enable_utc=True,
)

def run_async(coro):
    """
    Helper to run an async coroutine synchronously in the Celery worker thread/process.
    Reuses a single event loop to prevent asyncpg connection pool errors.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    return loop.run_until_complete(coro)

@celery_app.task(name="tasks.make_follow_up_call")
def make_follow_up_call(lead_id: int, attempt_number: int):
    """
    Pushes the lead into the Redis-based call queue and triggers the QueueDispatcher.
    Does NOT call Exotel directly.
    """
    print(f"[Celery Worker] Queueing follow-up call for Lead ID: {lead_id}, Attempt: {attempt_number}")
    
    # 1. Fetch current lead data
    lead = run_async(fetchrow("SELECT * FROM leads WHERE lead_id = $1;", lead_id))
    if not lead:
        print(f"[Celery Worker] Lead {lead_id} not found in database. Skipping.")
        return f"Lead {lead_id} not found."
        
    # 2. Check if lead is already converted or manually rejected
    status_lower = (lead.get("status") or "").lower()
    if status_lower in ["converted", "dnc", "do not call", "rejected"]:
        print(f"[Celery Worker] Lead {lead_id} is in status '{lead['status']}'. Skipping.")
        return f"Lead in '{lead['status']}' status. Skipped."
        
    # 3. Retrieve user's Exophone virtual number
    user_id = lead["user_id"]
    user_row = run_async(fetchrow("SELECT exotel_virtual_number FROM users WHERE user_id = $1", user_id))
    if not user_row or not user_row.get("exotel_virtual_number"):
        print(f"[Celery Worker] User {user_id} does not have an exotel virtual number assigned.")
        return "No exotel virtual number configured."
        
    exophone = user_row["exotel_virtual_number"]
    
    # 4. Push to Pending Queue in ChannelManager
    from services.telephony.channel_manager import ChannelManager
    from services.telephony.queue_dispatcher import QueueDispatcher
    
    channel_manager = ChannelManager()
    dispatcher = QueueDispatcher()
    
    # Initialize channels (in case they are not already initialized)
    run_async(channel_manager.initialize_channels())
    
    run_async(channel_manager.push_to_queue(lead_id, attempt_number, exophone))
    
    # 5. Trigger QueueDispatcher to assign call to a FREE channel
    run_async(dispatcher.dispatch())
    
    return f"Lead {lead_id} queued for {exophone}. Dispatcher triggered."

