from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ConditionalSpeed:
    speed: int
    days: List[str]
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    special: List[str] = None


def parse_conditional_speed(cond_str: str) -> ConditionalSpeed:
    if not cond_str:
        raise ValueError("Empty conditional string")

    cond_str = cond_str.replace("Conditional", "").strip()

    speed_part, period_part = cond_str.split("@")
    speed = int(speed_part.strip())

    period_part = period_part.strip().lstrip("(").rstrip(")")
    parts = [p.strip() for p in period_part.split(";")]

    days = []
    special = []
    start_time = None
    end_time = None

    for p in parts:
        if "-" in p and any(day in p for day in ["Mo","Tu","We","Th","Fr","Sa","Su"]):
            day_part, time_part = p.split(" ", 1)
            days.append(day_part)
            start_time, end_time = time_part.split("-")
        else:
            special.extend([d.strip() for d in p.split(",")])

    return ConditionalSpeed(
        speed=speed,
        days=days,
        start_time=start_time,
        end_time=end_time,
        special=special
    )