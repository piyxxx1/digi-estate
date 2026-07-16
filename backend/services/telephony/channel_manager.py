import os
import json
from datetime import datetime
from typing import Optional, Dict, List
from db.redis import get_redis_client
from db.postgresql import fetch, fetchrow, execute

def normalize_number(num: str) -> str:
    """Extracts the last 10 digits of a phone number for consistent normalization."""
    digits = "".join(c for c in (num or "") if c.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits

class ChannelManager:
    def __init__(self):
        self.redis = get_redis_client()
        # Redis Key Prefixes
        self.CHANNELS_ALL = "channels:all"
        self.CHANNELS_FREE = "channels:free"
        self.CHANNEL_INFO_PREFIX = "channel:info:"
        self.CALL_QUEUE_PREFIX = "call_queue:"
        self.CALL_SID_TO_CHANNEL = "call_sid_to_channel"
        
    async def initialize_channels(self, channels_per_num: int = 5):
        """
        Fetches all virtual numbers from exophone_pool and registers N channels for each in Redis.
        """
        try:
            rows = await fetch("SELECT phone_number FROM exophone_pool;")
            for row in rows:
                virtual_number = row["phone_number"]
                # Clean phone number for key compatibility
                clean_num = normalize_number(virtual_number)
                for i in range(1, channels_per_num + 1):
                    channel_id = f"chan_{clean_num}_{i}"
                    
                    # Register channel if not already exists in channels:all
                    if not self.redis.sismember(self.CHANNELS_ALL, channel_id):
                        self.redis.sadd(self.CHANNELS_ALL, channel_id)
                        self.redis.sadd(self.CHANNELS_FREE, channel_id)
                        
                        channel_info = {
                            "channel_id": channel_id,
                            "virtual_number": virtual_number,
                            "normalized_number": clean_num,
                            "status": "FREE",
                            "current_call_sid": "",
                            "last_updated": datetime.utcnow().isoformat()
                        }
                        self.redis.hset(f"{self.CHANNEL_INFO_PREFIX}{channel_id}", mapping=channel_info)
            print("[ChannelManager] Channels initialized successfully.")
        except Exception as e:
            print(f"[ChannelManager] Error initializing channels: {e}")

    async def get_channel_info(self, channel_id: str) -> Optional[Dict[str, str]]:
        """
        Retrieves channel details from Redis.
        """
        info = self.redis.hgetall(f"{self.CHANNEL_INFO_PREFIX}{channel_id}")
        return info if info else None

    async def push_to_queue(self, lead_id: int, attempt_number: int, virtual_number: str):
        """
        Pushes a lead to the pending queue for a specific virtual number.
        """
        payload = json.dumps({
            "lead_id": lead_id,
            "attempt_number": attempt_number,
            "virtual_number": virtual_number,
            "queued_at": datetime.utcnow().isoformat()
        })
        norm_number = normalize_number(virtual_number)
        key = f"{self.CALL_QUEUE_PREFIX}{norm_number}"
        self.redis.rpush(key, payload)
        print(f"[ChannelManager] Pushed Lead {lead_id} (Attempt {attempt_number}) to queue for {norm_number}")

    async def get_queue_length(self, virtual_number: str) -> int:
        norm_number = normalize_number(virtual_number)
        key = f"{self.CALL_QUEUE_PREFIX}{norm_number}"
        return self.redis.llen(key)

    async def get_free_channels_for_number(self, virtual_number: str) -> List[str]:
        """
        Returns all free channel IDs associated with a specific virtual number.
        """
        free_channels = self.redis.smembers(self.CHANNELS_FREE)
        norm_number = normalize_number(virtual_number)
        matching = []
        for chan_id in free_channels:
            info = await self.get_channel_info(chan_id)
            if info and info.get("normalized_number") == norm_number:
                matching.append(chan_id)
        return matching

    async def allocate_channel(self, channel_id: str, call_sid: str) -> bool:
        """
        Allocates a channel with the given CallSid, changing status to BUSY.
        Uses Redis lock to prevent race conditions.
        """
        lock_key = f"lock:channel:{channel_id}"
        with self.redis.lock(lock_key, timeout=5):
            # Verify channel is still free
            if not self.redis.sismember(self.CHANNELS_FREE, channel_id):
                return False
                
            self.redis.srem(self.CHANNELS_FREE, channel_id)
            self.redis.hset(f"{self.CHANNEL_INFO_PREFIX}{channel_id}", mapping={
                "status": "BUSY",
                "current_call_sid": call_sid,
                "last_updated": datetime.utcnow().isoformat()
            })
            # Add reverse mapping
            self.redis.hset(self.CALL_SID_TO_CHANNEL, call_sid, channel_id)
            return True

    async def release_channel_by_sid(self, call_sid: str) -> Optional[str]:
        """
        Releases the channel associated with the CallSid. Marks it FREE and clears CallSid.
        Returns the channel_id if released, None if not found.
        """
        channel_id = self.redis.hget(self.CALL_SID_TO_CHANNEL, call_sid)
        if not channel_id:
            return None

        lock_key = f"lock:channel:{channel_id}"
        with self.redis.lock(lock_key, timeout=5):
            # Double check current call_sid matches
            info = await self.get_channel_info(channel_id)
            if info and info.get("current_call_sid") == call_sid:
                self.redis.hset(f"{self.CHANNEL_INFO_PREFIX}{channel_id}", mapping={
                    "status": "FREE",
                    "current_call_sid": "",
                    "last_updated": datetime.utcnow().isoformat()
                })
                self.redis.sadd(self.CHANNELS_FREE, channel_id)
                self.redis.hdel(self.CALL_SID_TO_CHANNEL, call_sid)
                print(f"[ChannelManager] Channel {channel_id} released and marked FREE.")
                return channel_id
        return None
