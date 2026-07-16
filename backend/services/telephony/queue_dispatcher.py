import json
import redis
from datetime import datetime
from typing import Optional
from db.redis import get_redis_client
from db.postgresql import fetchrow, execute
from services.telephony.exotel_service import ExotelService
from services.telephony.channel_manager import ChannelManager, normalize_number

class QueueDispatcher:
    def __init__(self):
        self.redis = get_redis_client()
        self.channel_manager = ChannelManager()
        self.exotel_service = ExotelService()
        
    async def get_voice_app_url(self, exophone: str) -> Optional[str]:
        """
        Retrieves the voice application URL for a virtual number, using Redis cache to prevent excessive API requests.
        """
        cache_key = f"exophone_voice_url:{exophone}"
        url = self.redis.get(cache_key)
        if url:
            return url
            
        res = await self.exotel_service.get_available_numbers()
        if res and "numbers" in res:
            def last10(n):
                d = "".join(c for c in (n or "") if c.isdigit())
                return d[-10:] if len(d) >= 10 else d
            target = last10(exophone)
            for num in res["numbers"]:
                if last10(num.get("phone_number")) == target:
                    app_url = num.get("voice_url")
                    if app_url:
                        # Cache for 1 hour
                        self.redis.setex(cache_key, 3600, app_url)
                        return app_url
        return None

    async def dispatch(self):
        """
        Main dispatching logic. Group free channels by virtual number and process their queues.
        Ensures O(number_of_free_channels) complexity.
        """
        dispatch_lock = "lock:global_dispatcher"
        # Acquire global lock to prevent concurrent dispatcher runs
        try:
            with self.redis.lock(dispatch_lock, timeout=30, blocking_timeout=2):
                # 1. Fetch all free channels
                free_channels = list(self.redis.smembers(self.channel_manager.CHANNELS_FREE))
                if not free_channels:
                    print("[QueueDispatcher] No free channels available.")
                    return
                    
                # 2. Group free channels by virtual number
                by_number = {}
                for chan_id in free_channels:
                    info = await self.channel_manager.get_channel_info(chan_id)
                    if info and info.get("status") == "FREE":
                        v_num = info.get("virtual_number")
                        if v_num:
                            norm_num = normalize_number(v_num)
                            by_number.setdefault(norm_num, []).append(chan_id)
                            
                # 3. For each virtual number, dispatch leads up to the number of free channels
                for virtual_number, chan_ids in by_number.items():
                    queue_key = f"{self.channel_manager.CALL_QUEUE_PREFIX}{virtual_number}"
                    
                    while chan_ids:
                        # Check queue length first (O(1) operation)
                        q_len = await self.channel_manager.get_queue_length(virtual_number)
                        if q_len == 0:
                            break
                            
                        # Try to pop a lead
                        lead_data_str = self.redis.lpop(queue_key)
                        if not lead_data_str:
                            break
                            
                        lead_payload = json.loads(lead_data_str)
                        lead_id = lead_payload["lead_id"]
                        attempt_number = lead_payload["attempt_number"]
                        raw_virtual_number = lead_payload.get("virtual_number") or virtual_number
                        
                        chan_id = None
                        try:
                            # Fetch lead details from DB
                            lead = await fetchrow("SELECT phone_number, status, user_id FROM leads WHERE lead_id = $1;", lead_id)
                            if not lead:
                                print(f"[QueueDispatcher] Lead {lead_id} not found in DB. Skipping.")
                                continue
                                
                            status_lower = (lead.get("status") or "").lower()
                            if status_lower in ["converted", "dnc", "do not call", "rejected"]:
                                print(f"[QueueDispatcher] Lead {lead_id} is in final status '{lead['status']}'. Skipping.")
                                continue
                                
                            app_url = await self.get_voice_app_url(raw_virtual_number)
                            if not app_url:
                                print(f"[QueueDispatcher] App URL resolution failed for {raw_virtual_number}. Re-queuing lead.")
                                self.redis.lpush(queue_key, lead_data_str)
                                continue
                            
                            # Allocate a channel now that we have a valid lead
                            chan_id = chan_ids.pop(0)
                            
                            # Lock and allocate the channel temporarily as 'initiating'
                            allocated = await self.channel_manager.allocate_channel(chan_id, f"initiating_{lead_id}")
                            if not allocated:
                                # If channel was taken, put the lead back to queue and check another channel
                                self.redis.lpush(queue_key, lead_data_str)
                                continue
                                
                            # Format phone
                            phone_number = lead["phone_number"]
                            formatted_phone = "".join(c for c in phone_number if c.isdigit() or c == '+')
                            if len(formatted_phone) == 10 and not formatted_phone.startswith('+') and not formatted_phone.startswith('0'):
                                formatted_phone = '0' + formatted_phone
                            elif len(formatted_phone) == 12 and formatted_phone.startswith('91'):
                                formatted_phone = '+' + formatted_phone
                                
                            # Make Exotel Outbound Call
                            print(f"[QueueDispatcher] Dialing {formatted_phone} on channel {chan_id}...")
                            call_res = await self.exotel_service.make_outbound_ai_call(formatted_phone, raw_virtual_number, app_url)
                            
                            if "error" in call_res:
                                print(f"[QueueDispatcher] Call failed: {call_res['error']}. Re-queuing lead.")
                                await self.channel_manager.release_channel_by_sid(f"initiating_{lead_id}")
                                self.redis.lpush(queue_key, lead_data_str)
                                continue
                                
                            call_sid = call_res.get("Call", {}).get("Sid")
                            if not call_sid:
                                print(f"[QueueDispatcher] No CallSid returned by Exotel. Re-queuing lead.")
                                await self.channel_manager.release_channel_by_sid(f"initiating_{lead_id}")
                                self.redis.lpush(queue_key, lead_data_str)
                                continue
                                
                            # Successfully initiated. Update allocation with real CallSid
                            # First remove temporary mapping, then assign real CallSid
                            self.redis.hdel(self.channel_manager.CALL_SID_TO_CHANNEL, f"initiating_{lead_id}")
                            self.redis.hset(f"{self.channel_manager.CHANNEL_INFO_PREFIX}{chan_id}", mapping={
                                "current_call_sid": call_sid,
                                "last_updated": datetime.utcnow().isoformat()
                            })
                            self.redis.hset(self.channel_manager.CALL_SID_TO_CHANNEL, call_sid, chan_id)
                            
                            # Record call schedule and update lead in DB
                            await execute("""
                                UPDATE leads 
                                SET current_attempt = $1, 
                                    follow_up_status = $2 
                                WHERE lead_id = $3;
                            """, attempt_number, f"Attempt {attempt_number} Dialed", lead_id)
                            
                            print(f"[QueueDispatcher] Call initiated successfully. Sid: {call_sid} assigned to channel {chan_id}")
                            
                        except Exception as e:
                            print(f"[QueueDispatcher] Unexpected error processing lead {lead_id}: {e}")
                            if chan_id:
                                await self.channel_manager.release_channel_by_sid(f"initiating_{lead_id}")
                            self.redis.lpush(queue_key, lead_data_str)
                            
        except redis.exceptions.LockError:
            print("[QueueDispatcher] Could not acquire global dispatch lock (already running).")
        except Exception as e:
            import traceback
            print(f"[QueueDispatcher] Critical error during dispatch: {e}")
            traceback.print_exc()
