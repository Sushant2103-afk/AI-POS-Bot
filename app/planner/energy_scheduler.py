import json
from typing import List, Tuple, Dict, Any, Optional
from app.core.logging import logger

class EnergyScheduler:
    """
    Schedules tasks into free time blocks.
    Prioritizes high-energy, high-priority tasks during preferred study hours
    and automatically leaves buffer time to prevent burnout.
    """
    
    def __init__(self, buffer_ratio: float = 0.15):
        self.buffer_ratio = buffer_ratio

    def parse_peak_windows(self, peak_str: str) -> List[Tuple[int, int]]:
        """
        Parses comma-separated peak hours, e.g. "09:00-12:00,16:00-19:00" into minute ranges.
        """
        ranges = []
        if not peak_str:
            return ranges
            
        for block in peak_str.split(","):
            if "-" in block:
                try:
                    start_str, end_str = block.strip().split("-")
                    sh, sm = map(int, start_str.split(":"))
                    eh, em = map(int, end_str.split(":"))
                    ranges.append((sh * 60 + sm, eh * 60 + em))
                except Exception as e:
                    logger.warning(f"Error parsing peak window segment '{block}': {e}")
        return ranges

    def minutes_to_time(self, minutes: int) -> str:
        """Convert minutes from midnight to 'HH:MM' string."""
        hrs = minutes // 60
        mins = minutes % 60
        return f"{hrs:02d}:{mins:02d}"

    def get_overlap_score(self, start: int, end: int, peak_windows: List[Tuple[int, int]]) -> int:
        """
        Calculates how many minutes of the range [start, end] overlap with peak study windows.
        """
        overlap = 0
        for ps, pe in peak_windows:
            overlap_start = max(start, ps)
            overlap_end = min(end, pe)
            if overlap_start < overlap_end:
                overlap += (overlap_end - overlap_start)
        return overlap

    def schedule(
        self, 
        free_slots: List[Tuple[int, int]], 
        tasks: List[Any], 
        peak_str: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], List[Any]]:
        """
        Schedules a list of tasks into available free slots.
        Returns:
            - A list of scheduled study sessions containing {"task": task, "start_time": str, "end_time": str, ...}
            - A list of unscheduled tasks (spillover tasks).
        """
        # Default peak windows: morning (09:00-12:00) and evening (16:00-19:00)
        peak_windows = self.parse_peak_windows(peak_str) if peak_str else [(540, 720), (960, 1140)]

        # Calculate time parameters
        total_free_mins = sum(end - start for start, end in free_slots)
        buffer_mins = int(total_free_mins * self.buffer_ratio)
        max_schedulable_mins = total_free_mins - buffer_mins

        logger.info(f"Scheduling: Total Free = {total_free_mins}m, Buffer = {buffer_mins}m, Max Study = {max_schedulable_mins}m")

        # Sort tasks: Priority first (high -> medium -> low), then Energy (high -> medium -> low)
        priority_map = {"high": 3, "medium": 2, "low": 1}
        energy_map = {"high": 3, "medium": 2, "low": 1}

        def get_task_sort_key(t):
            # Primary Roadmap Tasks & Revisions take tier 2 precedence over Sunday preset activities (tier 1)
            is_sunday = getattr(t, "is_sunday_activity", False) or (
                hasattr(t, "topic") and t.topic and t.topic.title == "Sunday Activities"
            )
            tier_score = 1 if is_sunday else 2

            rm_prio = 1
            if hasattr(t, "topic") and t.topic and hasattr(t.topic, "roadmap") and t.topic.roadmap:
                rm_prio = getattr(t.topic.roadmap, "priority", 1) or 1
            rm_score = max(0, 100 - rm_prio)
            p_score = priority_map.get(str(getattr(t, "priority", "medium")).lower(), 2)
            e_score = energy_map.get(str(getattr(t, "energy_level", "medium")).lower(), 2)
            return (tier_score, rm_score, p_score, e_score)

        sorted_tasks = sorted(
            tasks,
            key=get_task_sort_key,
            reverse=True
        )

        scheduled_sessions = []
        unscheduled_tasks = []
        
        # Represent free space as mutable intervals: [start_min, end_min]
        space_blocks = [[start, end] for start, end in free_slots]
        scheduled_minutes = 0

        for task in sorted_tasks:
            task_duration = getattr(task, "estimated_minutes", 60)
            
            # Check capacity limits
            if scheduled_minutes + task_duration > max_schedulable_mins:
                logger.info(f"Task '{getattr(task, 'title', '')}' skipped due to study capacity limit reached.")
                unscheduled_tasks.append(task)
                continue

            is_high_energy = getattr(task, "energy_level", "medium").lower() == "high"
            best_block_idx = -1
            best_placement_start = -1
            best_score = -1

            # Find matching slot block
            for idx, block in enumerate(space_blocks):
                start, end = block
                block_capacity = end - start
                
                if block_capacity >= task_duration:
                    if is_high_energy:
                        # For high energy, we want maximum overlap with peak study hours
                        # We evaluate placing the task at the start of the block
                        overlap_score = self.get_overlap_score(start, start + task_duration, peak_windows)
                        if overlap_score > best_score:
                            best_score = overlap_score
                            best_block_idx = idx
                            best_placement_start = start
                    else:
                        # For non-high energy tasks, prefer non-peak windows to preserve peak capacity
                        # i.e., minimize peak overlap score
                        overlap_score = self.get_overlap_score(start, start + task_duration, peak_windows)
                        score = 1440 - overlap_score # higher score means lower peak overlap
                        if score > best_score:
                            best_score = score
                            best_block_idx = idx
                            best_placement_start = start

            # Fallback if no specific peak matches but space is available
            if best_block_idx == -1:
                # Find first block with space
                for idx, block in enumerate(space_blocks):
                    start, end = block
                    if end - start >= task_duration:
                        best_block_idx = idx
                        best_placement_start = start
                        break

            if best_block_idx != -1:
                # Place task
                session_start = best_placement_start
                session_end = session_start + task_duration
                
                scheduled_sessions.append({
                    "task": task,
                    "start_time": self.minutes_to_time(session_start),
                    "end_time": self.minutes_to_time(session_end),
                    "start_minutes": session_start,
                    "end_minutes": session_end
                })

                scheduled_minutes += task_duration

                # Update the block (remove scheduled range)
                block_start, block_end = space_blocks[best_block_idx]
                if session_start == block_start:
                    # Shrink from left
                    space_blocks[best_block_idx][0] = session_end
                elif session_end == block_end:
                    # Shrink from right
                    space_blocks[best_block_idx][1] = session_start
                else:
                    # Split block
                    space_blocks[best_block_idx] = [block_start, session_start]
                    space_blocks.insert(best_block_idx + 1, [session_end, block_end])
            else:
                # No slot large enough to fit task
                logger.info(f"Task '{getattr(task, 'title', '')}' could not fit in any remaining free slot block.")
                unscheduled_tasks.append(task)

        # Sort scheduled sessions chronologically
        scheduled_sessions.sort(key=lambda s: s["start_minutes"])
        return scheduled_sessions, unscheduled_tasks
