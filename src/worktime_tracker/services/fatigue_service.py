"""Seven-day workload indicator; this is not medical advice."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from worktime_tracker.models import WorkRecord
from .worktime_calculator import calculate_work_minutes
@dataclass(frozen=True)
class FatigueResult:
    score: int
    level: str
    reasons: tuple[str, ...]
def calculate_fatigue_score(records: list[WorkRecord], standard_daily: int = 480, workdays_per_week: int = 5) -> FatigueResult:
    rows = sorted(records, key=lambda r: r.work_date)[-7:]
    actual = [calculate_work_minutes(r) for r in rows]
    weekly = standard_daily * workdays_per_week
    a = 30 * min(max(((sum(actual) / weekly if weekly else 1) - 1) / .3, 0), 1)
    overtime = sum(max(v-r.standard_minutes, 0) for v, r in zip(actual, rows))
    b = 25 * min(overtime / 600, 1)
    streak = 0
    for r in reversed(rows):
        if calculate_work_minutes(r) > 0: streak += 1
        else: break
    c = 0 if streak <= 5 else min((streak - 5) * 5, 20)
    short_rest = 0
    for previous, current in zip(rows, rows[1:]):
        end = datetime.combine(previous.work_date, datetime.strptime(previous.clock_out or "00:00", "%H:%M").time()) + (timedelta(days=1) if previous.overnight else timedelta())
        start = datetime.combine(current.work_date, datetime.strptime(current.clock_in or "00:00", "%H:%M").time())
        short_rest += (start-end < timedelta(hours=11))
    d = min(short_rest*5, 15)
    late = sum((r.clock_out or "00:00") >= "21:00" for r in rows); e = min(late*2, 10)
    score = max(0, min(100, round(a+b+c+d+e)))
    level = "低" if score < 30 else "中度" if score < 50 else "偏高" if score < 70 else "高"
    reasons=[]
    if a: reasons.append("最近7日工作時數偏高")
    if streak > 5: reasons.append(f"已連續工作{streak}天")
    if short_rest: reasons.append(f"有{short_rest}次工作間隔低於11小時")
    if late: reasons.append(f"有{late}次晚間下班")
    return FatigueResult(score, level, tuple(reasons))
