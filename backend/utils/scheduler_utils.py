import random
from datetime import datetime, timedelta, time
from typing import Tuple

def calculate_next_working_time(base_time: datetime, delay_minutes: int) -> Tuple[datetime, bool]:
    """
    Calculates the next valid execution time based on business hours.
    Business hours: 9:00 AM - 6:00 PM, Monday to Friday.
    If the time is shifted to a new day due to non-working hours, it picks a random 
    time between 9:00 AM and 6:00 PM and returns (time, is_shifted).
    """
    START_HOUR = 9
    END_HOUR = 18
    is_shifted = False
    
    # 1. Add the delay to the base time
    target_time = base_time + timedelta(minutes=delay_minutes)
    
    while True:
        # Check day of week (0 = Monday, 6 = Sunday)
        day_of_week = target_time.weekday()
        
        # If Weekend (Saturday/Sunday), shift to Monday at random time
        if day_of_week >= 5:
            is_shifted = True
            days_to_add = 7 - day_of_week
            random_hour = random.randint(START_HOUR, END_HOUR - 1)
            random_minute = random.randint(0, 59)
            target_time = target_time.replace(
                hour=random_hour, minute=random_minute, second=0, microsecond=0
            ) + timedelta(days=days_to_add)
            continue
            
        t_time = target_time.time()
        
        # If before 9:00 AM, move to random time on the same day
        if t_time < time(START_HOUR, 0):
            is_shifted = True
            random_hour = random.randint(START_HOUR, END_HOUR - 1)
            random_minute = random.randint(0, 59)
            target_time = target_time.replace(hour=random_hour, minute=random_minute, second=0, microsecond=0)
        
        # If at or after 6:00 PM, move to random time the next day
        elif t_time >= time(END_HOUR, 0):
            is_shifted = True
            random_hour = random.randint(START_HOUR, END_HOUR - 1)
            random_minute = random.randint(0, 59)
            target_time = target_time.replace(
                hour=random_hour, minute=random_minute, second=0, microsecond=0
            ) + timedelta(days=1)
            
        else:
            # The time is within 9:00 AM - 6:00 PM on a weekday
            break
            
    return target_time, is_shifted
