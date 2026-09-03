"""Standard-library monthly and yearly aggregations."""

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import mean
from worktime_tracker.models import WorkRecord
from .worktime_calculator import calculate_work_minutes


@dataclass(frozen=True)
class Summary:
    work_minutes: int
    standard_minutes: int
    difference: int
    workdays: int
    average_minutes: int
    longest_date: str | None
    longest_minutes: int
    overtime_minutes: int
    shortfall_minutes: int
    holiday_work_minutes: int = 0


def summarize(records: list[WorkRecord], calendar=None, start=None, end=None, today=None) -> Summary:
    values = [(r, calculate_work_minutes(r)) for r in records]
    total = sum(v for _, v in values)
    standard = sum((calendar.standard_minutes_for(r.work_date) if calendar else r.standard_minutes) for r, _ in values)
    longest = max(values, key=lambda x: x[1], default=None)
    differences = [value - (calendar.standard_minutes_for(record.work_date) if calendar else record.standard_minutes) for record, value in values]
    missing_shortfall = 0
    if calendar and start and end:
        effective_end = min(end, (today or date.today()) - timedelta(days=1))
        missing_shortfall = sum(calendar.standard_minutes_for(day) for day in calendar.get_missing_workdays(start, effective_end, records))
    return Summary(
        total,
        standard + missing_shortfall,
        total - standard - missing_shortfall,
        sum(value > 0 for _, value in values),
        round(mean([v for _, v in values if v > 0])) if any(v > 0 for _, v in values) else 0,
        longest[0].work_date.isoformat() if longest else None,
        longest[1] if longest else 0,
        sum(max(value, 0) for value in differences),
        sum(max(-value, 0) for value in differences) + missing_shortfall,
        sum(
            value
            for record, value in values
            if calendar and calendar.standard_minutes_for(record.work_date) == 0
        ),
    )


def calculate_month_summary(
    records: list[WorkRecord], year: int, month: int, calendar=None, today=None,
    tracking_start_date=None,
) -> Summary:
    from calendar import monthrange
    start, end = date(year, month, 1), date(year, month, monthrange(year, month)[1])
    if tracking_start_date:
        start = max(start, tracking_start_date)
    return summarize([r for r in records if r.work_date.year == year and r.work_date.month == month], calendar, start, end, today)


def calculate_year_summary(records: list[WorkRecord], year: int) -> Summary:
    return summarize([r for r in records if r.work_date.year == year])


def calculate_conversion_summary(entries, year: int) -> dict[str, int]:
    """Conversion totals are distinct from leave usage totals."""
    from worktime_tracker.models import LeaveType, TransactionType

    comp_to_annual = annual_to_comp = 0
    for entry in entries:
        if (
            entry.entry_date.year != year
            or entry.transaction_type != TransactionType.LEAVE_CONVERSION
        ):
            continue
        if entry.source_leave_type == LeaveType.COMP_TIME:
            comp_to_annual += entry.source_minutes or 0
        elif entry.source_leave_type == LeaveType.ANNUAL_LEAVE:
            annual_to_comp += entry.source_minutes or 0
    return {
        "comp_to_annual_minutes": comp_to_annual,
        "annual_to_comp_minutes": annual_to_comp,
    }
