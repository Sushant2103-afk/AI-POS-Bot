import json
from datetime import date, datetime, timedelta
from typing import List, Tuple, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.core import Users, Settings, Timetable, Holidays, Events
from app.core.logging import logger

class TimeAllocator:
    """
    Time Block Allocator engine.
    Computes free time windows available for study on a given date by subtracting sleep,
    lectures, events, meals, and gym periods.
    """
    
    def __init__(self, db: Session):
        self.db = db

    def time_to_minutes(self, t_str: str) -> int:
        """Convert 'HH:MM' string to minutes from midnight."""
        parts = t_str.strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])

    def minutes_to_time(self, minutes: int) -> str:
        """Convert minutes from midnight to 'HH:MM' string."""
        hrs = minutes // 60
        mins = minutes % 60
        return f"{hrs:02d}:{mins:02d}"

    def get_blocked_intervals(self, user_id: int, target_date: date) -> List[Tuple[int, int]]:
        """
        Gathers all blocked time intervals (in minutes from midnight) for a user on a given date.
        """
        user = self.db.query(Users).filter(Users.id == user_id).first()
        if not user:
            raise ValueError(f"User with ID {user_id} not found.")

        blocked = []

        # 1. Sleep window: midnight to wake_up_time, and sleep_time to midnight
        wake_min = self.time_to_minutes(user.wake_up_time or "07:00")
        sleep_min = self.time_to_minutes(user.sleep_time or "23:00")

        # Guard: sleep_time of '00:00' means midnight and would block entire day; treat as 23:00
        if sleep_min == 0:
            sleep_min = 23 * 60  # default to 23:00
        
        # Block early morning sleep [0, wake_up_time]
        blocked.append((0, wake_min))
        # Block late night sleep [sleep_time, 1440]
        blocked.append((sleep_min, 1440))

        # 2. Settings: Gym & Meals
        user_settings = self.db.query(Settings).filter(Settings.user_id == user_id).all()
        settings_dict = {s.key: s.value for s in user_settings}

        # Default time configurations
        gym_time = settings_dict.get("gym_time", "18:00-19:00")
        breakfast_time = settings_dict.get("breakfast_time", "08:00-08:45")
        lunch_time = settings_dict.get("lunch_time", "13:00-14:00")
        dinner_time = settings_dict.get("dinner_time", "20:00-21:00")

        for time_range in [gym_time, breakfast_time, lunch_time, dinner_time]:
            if "-" in time_range:
                try:
                    start_str, end_str = time_range.split("-")
                    blocked.append((self.time_to_minutes(start_str), self.time_to_minutes(end_str)))
                except Exception as e:
                    logger.warning(f"Failed to parse block settings time range '{time_range}': {e}")

        # 3. Check Holiday: If it is a holiday, ignore regular college class timetable
        is_holiday = self.db.query(Holidays).filter(
            Holidays.user_id == user_id,
            Holidays.date == target_date
        ).first() is not None

        if not is_holiday:
            # Load classes from Timetable
            # weekday() returns 0 for Monday, 6 for Sunday
            day_num = target_date.weekday()
            classes = self.db.query(Timetable).filter(
                Timetable.user_id == user_id,
                Timetable.day_of_week == day_num
            ).all()
            for cls in classes:
                try:
                    start_min = self.time_to_minutes(cls.start_time)
                    end_min = self.time_to_minutes(cls.end_time)
                    blocked.append((start_min, end_min))
                except Exception as e:
                    logger.error(f"Error parsing timetable class '{cls.activity_name}': {e}")

        # 4. Calendar Events (which block time)
        # Fetch events overlapping with target_date
        day_start = datetime.combine(target_date, datetime.min.time())
        day_end = datetime.combine(target_date, datetime.max.time())
        
        events = self.db.query(Events).filter(
            Events.user_id == user_id,
            Events.is_blocked_time == True,
            Events.start_time < day_end,
            Events.end_time > day_start
        ).all()

        for ev in events:
            # Find overlap range within target_date
            ev_start = max(ev.start_time, day_start)
            ev_end = min(ev.end_time, day_end)
            
            # Map datetimes to minutes of day
            start_min = ev_start.hour * 60 + ev_start.minute
            end_min = ev_end.hour * 60 + ev_end.minute
            # If end time is midnight of next day, cap it at 1440
            if ev_end.date() > target_date:
                end_min = 1440
            blocked.append((start_min, end_min))

        return self.merge_intervals(blocked)

    def merge_intervals(self, intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """
        Merge overlapping time intervals.
        """
        if not intervals:
            return []
            
        # Clean and sort intervals
        valid_intervals = []
        for start, end in intervals:
            if start < end:
                valid_intervals.append((max(0, start), min(1440, end)))
                
        valid_intervals.sort(key=lambda x: x[0])
        
        merged = [valid_intervals[0]]
        for current in valid_intervals[1:]:
            last_start, last_end = merged[-1]
            current_start, current_end = current
            
            if current_start <= last_end:
                # Overlap, merge them
                merged[-1] = (last_start, max(last_end, current_end))
            else:
                merged.append(current)
                
        return merged

    def get_free_slots(self, user_id: int, target_date: date) -> List[Tuple[int, int]]:
        """
        Calculates available free study slots (as minute intervals) by inverting blocked slots.
        """
        blocked = self.get_blocked_intervals(user_id, target_date)
        
        free_slots = []
        current_pointer = 0
        
        for start, end in blocked:
            if start > current_pointer:
                free_slots.append((current_pointer, start))
            current_pointer = max(current_pointer, end)
            
        if current_pointer < 1440:
            free_slots.append((current_pointer, 1440))
            
        return free_slots

    def get_available_study_hours(self, user_id: int, target_date: date) -> float:
        """
        Calculate total study hours available in free slots.
        """
        slots = self.get_free_slots(user_id, target_date)
        total_mins = sum(end - start for start, end in slots)
        return total_mins / 60.0
