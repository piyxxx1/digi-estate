from typing import List, Dict
import asyncio
from db.redis import RedisService
from models.request_models import ChatMessage
from db.postgresql import fetchrow, execute

class MemoryManager:
    def __init__(self):
        self.redis_service = RedisService()

    def save_interaction(self, user_id: str, role: str, message: str):
        self.redis_service.save_message(user_id, role, message)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._save_to_postgres(user_id, role, message))
        except RuntimeError:
            pass

    async def _save_to_postgres(self, call_sid: str, role: str, message: str):
        if not call_sid or call_sid.startswith("mock_") or call_sid == "default_user":
            return
            
        try:
            row = await fetchrow("SELECT phone_number, to_phone_number, direction FROM calls WHERE call_sid = $1", call_sid)
            if not row:
                return
                
            lead_phone = row["phone_number"]
            if not lead_phone:
                return
                
            clean_phone = "".join(c for c in lead_phone if c.isdigit())
            suffix = f"%{clean_phone[-10:]}" if len(clean_phone) >= 10 else f"%{clean_phone}"
            
            lead_row = await fetchrow("SELECT user_id FROM leads WHERE phone_number LIKE $1 OR phone_number LIKE $2 LIMIT 1;", f"%{clean_phone}", suffix)
            
            if lead_row and lead_row["user_id"]:
                db_user_id = lead_row["user_id"]
            else:
                user_row = await fetchrow("SELECT user_id FROM users LIMIT 1")
                if user_row:
                    db_user_id = user_row["user_id"]
                else:
                    return

            await execute("""
                INSERT INTO conversations (user_id, phone_number, role, message)
                VALUES ($1, $2, $3, $4, $5)
            """, db_user_id, lead_phone, role, message, call_sid)
        except Exception as e:
            print(f"[Memory Manager] DB Error inserting into conversations: {e}")

    def get_history(self, user_id: str, limit: int = 10) -> List[ChatMessage]:
        recent_messages = self.redis_service.get_recent_messages(user_id, limit=limit)
        return [
            ChatMessage(role="user" if msg["role"] == "user" else "assistant", text=msg["message"])
            for msg in recent_messages
        ]

    def clear_memory(self, user_id: str):
        # Implementation for clearing history if needed
        pass
