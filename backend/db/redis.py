import os
import json
import redis
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

def get_redis_client(socket_timeout: float = 0.5):
    """
    Creates and returns a connection client to Redis with configuration timeouts.
    """
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD,
        decode_responses=True,
        socket_timeout=socket_timeout,
        socket_connect_timeout=socket_timeout
    )

class RedisService:
    def __init__(self):
        self.redis_client = get_redis_client()
        # In-memory fallback when Redis is unavailable
        self._memory_store: Dict[str, list] = {}
        self._redis_available = True

    def _check_redis(self) -> bool:
        """Quick ping to check if Redis is reachable."""
        if not self._redis_available:
            return False
        try:
            self.redis_client.ping()
            self._redis_available = True
            return True
        except Exception:
            if self._redis_available:
                print("[Redis] Not available — using in-memory fallback for this call")
            self._redis_available = False
            return False

    def save_message(self, user_id: str, role: str, message: str):
        """
        Saves a message to the conversation history in Redis.
        Falls back to in-memory store if Redis is unavailable.
        role: "user" or "assistant"
        """
        data = {
            "role": role,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        key = f"conversation:{user_id}"

        if self._check_redis():
            try:
                self.redis_client.rpush(key, json.dumps(data))
                # Limit Redis memory - keep only latest 50 messages
                self.redis_client.ltrim(key, -50, -1)
                return
            except Exception as e:
                print(f"[Redis] Save error: {e} — switching to memory fallback")

        # In-memory fallback
        if key not in self._memory_store:
            self._memory_store[key] = []
        self._memory_store[key].append(data)
        # Keep only last 50
        self._memory_store[key] = self._memory_store[key][-50:]

    def get_recent_messages(self, user_id: str, limit: int = 10) -> List[Dict]:
        """
        Fetches the most recent messages from the conversation history.
        Falls back to in-memory store if Redis is unavailable.
        """
        key = f"conversation:{user_id}"

        if self._check_redis():
            try:
                messages = self.redis_client.lrange(key, -limit, -1)
                return [json.loads(msg) for msg in messages]
            except Exception as e:
                print(f"[Redis] Get error: {e} — using memory fallback")

        # In-memory fallback
        messages = self._memory_store.get(key, [])
        return messages[-limit:]

    def clear_history(self, user_id: str):
        """Clears the conversation history for a specific user."""
        key = f"conversation:{user_id}"

        try:
            self.redis_client.delete(key)
        except Exception:
            pass

        # Clear in-memory too
        self._memory_store.pop(key, None)
