"""Pure minute-based work-time calculations."""
from datetime import datetime, timedelta
from worktime_tracker.models import WorkRecord

class ValidationError(ValueError):
    """A user-correctable input error."""

def _at(day, value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%H:%M").time()
    except (TypeError, ValueError) as exc:
        raise ValidationError("時間格式必須為 HH:MM。") from exc
    return datetime.combine(day, parsed)

def calculate_lunch_overlap(work_start: datetime, work_end: datetime, break_start: datetime, break_end: datetime) -> int:
    if break_end < break_start:
        raise ValidationError("午休結束時間不可早於開始時間。")
    return max(0, int((min(work_end, break_end) - max(work_start, break_start)).total_seconds() // 60))

def calculate_work_minutes(record: WorkRecord) -> int:
    if not record.clock_in or not record.clock_out:
        raise ValidationError("請輸入上班與下班時間。")
    start = _at(record.work_date, record.clock_in)
    end = _at(record.work_date, record.clock_out)
    if end < start:
        if not record.overnight:
            raise ValidationError("下班時間不可早於上班時間，若為跨日班請開啟跨日班。")
        end += timedelta(days=1)
    raw = int((end - start).total_seconds() // 60)
    overlap = 0
    if record.deduct_break and record.break_start and record.break_end:
        break_start = _at(record.work_date, record.break_start)
        break_end = _at(record.work_date, record.break_end)
        overlap = calculate_lunch_overlap(start, end, break_start, break_end)
    return raw - overlap

def calculate_daily_difference(actual_minutes: int, standard_minutes: int) -> int:
    if standard_minutes < 0:
        raise ValidationError("每日標準工時不可為負數。")
    return actual_minutes - standard_minutes
