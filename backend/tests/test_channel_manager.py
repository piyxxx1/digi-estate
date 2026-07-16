import asyncio
import json
import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime



from services.telephony.channel_manager import ChannelManager, normalize_number
from services.telephony.queue_dispatcher import QueueDispatcher
from db.redis import get_redis_client

class TestChannelManagerAndDispatcher(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.redis = get_redis_client()
        # Clean test keys
        self.redis.delete("channels:all")
        self.redis.delete("channels:free")
        self.redis.delete("call_sid_to_channel")
        for key in self.redis.keys("channel:info:*"):
            self.redis.delete(key)
        for key in self.redis.keys("call_queue:*"):
            self.redis.delete(key)
            
        self.channel_manager = ChannelManager()
        
        # Override initialize_channels to use a static mock exophone number
        # to avoid calling DB
        self.virtual_number = "+911141187680"
        
    async def asyncTearDown(self):
        # Cleanup
        self.redis.delete("channels:all")
        self.redis.delete("channels:free")
        self.redis.delete("call_sid_to_channel")
        for key in self.redis.keys("channel:info:*"):
            self.redis.delete(key)
        for key in self.redis.keys("call_queue:*"):
            self.redis.delete(key)

    async def register_mock_channels(self, count: int):
        clean_num = normalize_number(self.virtual_number)
        for i in range(1, count + 1):
            channel_id = f"chan_{clean_num}_{i}"
            self.redis.sadd(self.channel_manager.CHANNELS_ALL, channel_id)
            self.redis.sadd(self.channel_manager.CHANNELS_FREE, channel_id)
            channel_info = {
                "channel_id": channel_id,
                "virtual_number": self.virtual_number,
                "normalized_number": clean_num,
                "status": "FREE",
                "current_call_sid": "",
                "last_updated": datetime.utcnow().isoformat()
            }
            self.redis.hset(f"{self.channel_manager.CHANNEL_INFO_PREFIX}{channel_id}", mapping=channel_info)

    @patch('services.telephony.queue_dispatcher.fetchrow')
    @patch('services.telephony.queue_dispatcher.execute')
    async def test_single_channel_scenario(self, mock_execute, mock_fetchrow):
        # 1. Register 1 channel
        await self.register_mock_channels(1)
        
        # 2. Push 1 lead to queue
        await self.channel_manager.push_to_queue(lead_id=101, attempt_number=1, virtual_number=self.virtual_number)
        
        # Mock database lead retrieval
        mock_fetchrow.return_value = {
            "phone_number": "9999999999",
            "status": "New",
            "user_id": "user1"
        }
        
        # Mock Exotel service API response
        dispatcher = QueueDispatcher()
        dispatcher.exotel_service.make_outbound_ai_call = AsyncMock(return_value={
            "Call": {"Sid": "mock_call_sid_101"}
        })
        dispatcher.get_voice_app_url = AsyncMock(return_value="https://exotel.com/app")
        
        # 3. Dispatch
        await dispatcher.dispatch()
        
        # 4. Verify channel is busy and has call SID
        free_chans = self.redis.smembers(self.channel_manager.CHANNELS_FREE)
        self.assertEqual(len(free_chans), 0) # No free channels remaining
        
        clean_num = normalize_number(self.virtual_number)
        chan_info = await self.channel_manager.get_channel_info(f"chan_{clean_num}_1")
        self.assertEqual(chan_info["status"], "BUSY")
        self.assertEqual(chan_info["current_call_sid"], "mock_call_sid_101")
        
        # Verify DB updates were executed
        mock_execute.assert_called_once()
        self.assertIn("Attempt 1 Dialed", mock_execute.call_args[0])

    @patch('services.telephony.queue_dispatcher.fetchrow')
    @patch('services.telephony.queue_dispatcher.execute')
    async def test_multiple_channels_scenario(self, mock_execute, mock_fetchrow):
        # 1. Register 3 channels
        await self.register_mock_channels(3)
        
        # 2. Push 3 leads
        for lead_id in [201, 202, 203]:
            await self.channel_manager.push_to_queue(lead_id=lead_id, attempt_number=1, virtual_number=self.virtual_number)
            
        mock_fetchrow.side_effect = [
            {"phone_number": "9999999901", "status": "New", "user_id": "user1"},
            {"phone_number": "9999999902", "status": "New", "user_id": "user1"},
            {"phone_number": "9999999903", "status": "New", "user_id": "user1"},
        ]
        
        dispatcher = QueueDispatcher()
        dispatcher.get_voice_app_url = AsyncMock(return_value="https://exotel.com/app")
        
        # Return unique CallSids
        sids = ["sid_201", "sid_202", "sid_203"]
        def mock_call(*args, **kwargs):
            sid = sids.pop(0)
            return {"Call": {"Sid": sid}}
        dispatcher.exotel_service.make_outbound_ai_call = AsyncMock(side_effect=mock_call)
        
        # 3. Dispatch
        await dispatcher.dispatch()
        
        # 4. Verify all channels are busy
        free_chans = self.redis.smembers(self.channel_manager.CHANNELS_FREE)
        self.assertEqual(len(free_chans), 0)
        
        # Verify map size is 3
        map_size = self.redis.hlen(self.channel_manager.CALL_SID_TO_CHANNEL)
        self.assertEqual(map_size, 3)

    @patch('services.telephony.queue_dispatcher.fetchrow')
    @patch('services.telephony.queue_dispatcher.execute')
    async def test_channel_busy_overflow_scenario(self, mock_execute, mock_fetchrow):
        # 1. Register 2 channels
        await self.register_mock_channels(2)
        
        # 2. Push 5 leads
        for lead_id in [301, 302, 303, 304, 305]:
            await self.channel_manager.push_to_queue(lead_id=lead_id, attempt_number=1, virtual_number=self.virtual_number)
            
        mock_fetchrow.side_effect = [
            {"phone_number": "9999999901", "status": "New", "user_id": "user1"},
            {"phone_number": "9999999902", "status": "New", "user_id": "user1"},
        ]
        
        dispatcher = QueueDispatcher()
        dispatcher.get_voice_app_url = AsyncMock(return_value="https://exotel.com/app")
        sids = ["sid_301", "sid_302"]
        dispatcher.exotel_service.make_outbound_ai_call = AsyncMock(side_effect=lambda *a, **k: {"Call": {"Sid": sids.pop(0)}})
        
        # 3. Dispatch
        await dispatcher.dispatch()
        
        # 4. Verify 2 channels occupied, 3 leads remaining in queue
        free_chans = self.redis.smembers(self.channel_manager.CHANNELS_FREE)
        self.assertEqual(len(free_chans), 0)
        
        q_len = await self.channel_manager.get_queue_length(self.virtual_number)
        self.assertEqual(q_len, 3)

    async def test_simultaneous_webhook_events(self):
        # 1. Register 2 channels and allocate them
        await self.register_mock_channels(2)
        clean_num = normalize_number(self.virtual_number)
        chan1 = f"chan_{clean_num}_1"
        chan2 = f"chan_{clean_num}_2"
        
        await self.channel_manager.allocate_channel(chan1, "sid_abc")
        await self.channel_manager.allocate_channel(chan2, "sid_xyz")
        
        # 2. Simulate simultaneous release calls (async)
        # Using gather to execute them concurrently
        results = await asyncio.gather(
            self.channel_manager.release_channel_by_sid("sid_abc"),
            self.channel_manager.release_channel_by_sid("sid_xyz"),
            self.channel_manager.release_channel_by_sid("nonexistent_sid")
        )
        
        # 3. Verify results
        self.assertEqual(results[0], chan1)
        self.assertEqual(results[1], chan2)
        self.assertIsNone(results[2])
        
        # 4. Verify both are FREE again
        free_chans = self.redis.smembers(self.channel_manager.CHANNELS_FREE)
        self.assertEqual(len(free_chans), 2)
        self.assertIn(chan1, free_chans)
        self.assertIn(chan2, free_chans)

    @patch('services.telephony.queue_dispatcher.fetchrow')
    @patch('services.telephony.queue_dispatcher.execute')
    async def test_1000_scheduled_leads(self, mock_execute, mock_fetchrow):
        # 1. Register 5 channels
        await self.register_mock_channels(5)
        
        # 2. Push 1000 leads
        for lead_id in range(1, 1001):
            await self.channel_manager.push_to_queue(lead_id=lead_id, attempt_number=1, virtual_number=self.virtual_number)
            
        # Mock DB response for the first 5 leads
        mock_fetchrow.return_value = {"phone_number": "9999999999", "status": "New", "user_id": "user1"}
        
        dispatcher = QueueDispatcher()
        dispatcher.get_voice_app_url = AsyncMock(return_value="https://exotel.com/app")
        sids = [f"sid_{i}" for i in range(1, 6)]
        dispatcher.exotel_service.make_outbound_ai_call = AsyncMock(side_effect=lambda *a, **k: {"Call": {"Sid": sids.pop(0)}})
        
        # 3. Dispatch
        await dispatcher.dispatch()
        
        # 4. Verify exactly 5 channels occupied, 995 leads remaining in queue
        free_chans = self.redis.smembers(self.channel_manager.CHANNELS_FREE)
        self.assertEqual(len(free_chans), 0)
        
        q_len = await self.channel_manager.get_queue_length(self.virtual_number)
        self.assertEqual(q_len, 995)
        
        # 5. Release one channel (e.g. sid_3)
        released = await self.channel_manager.release_channel_by_sid("sid_3")
        self.assertIsNotNone(released)
        
        # Now we have 1 free channel
        free_chans = self.redis.smembers(self.channel_manager.CHANNELS_FREE)
        self.assertEqual(len(free_chans), 1)
        
        # Mock next call
        dispatcher.exotel_service.make_outbound_ai_call = AsyncMock(return_value={"Call": {"Sid": "sid_new"}})
        
        # 6. Dispatch again
        await dispatcher.dispatch()
        
        # 7. Verify queue size decreased to 994 and channel is busy again
        free_chans = self.redis.smembers(self.channel_manager.CHANNELS_FREE)
        self.assertEqual(len(free_chans), 0)
        q_len = await self.channel_manager.get_queue_length(self.virtual_number)
        self.assertEqual(q_len, 994)

if __name__ == '__main__':
    unittest.main()
