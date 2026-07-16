import sys
import os
import time

# Add backend directory to sys.path
sys.path.append(os.path.abspath('.'))

from db.redis import RedisService

print("Initializing RedisService...")
start = time.perf_counter()
service = RedisService()
print(f"Initialized in {(time.perf_counter() - start)*1000:.2f}ms")

print("Calling get_recent_messages (1st time)...")
start = time.perf_counter()
service.get_recent_messages("test_user")
print(f"Completed in {(time.perf_counter() - start)*1000:.2f}ms")

print("Calling save_message...")
start = time.perf_counter()
service.save_message("test_user", "user", "hello")
print(f"Completed in {(time.perf_counter() - start)*1000:.2f}ms")

print("Calling get_recent_messages (2nd time)...")
start = time.perf_counter()
service.get_recent_messages("test_user")
print(f"Completed in {(time.perf_counter() - start)*1000:.2f}ms")
