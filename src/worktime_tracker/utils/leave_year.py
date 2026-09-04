"""Leave-year range calculations driven by the configured settlement day."""

from calendar import monthrange
from datetime import date, timedelta


def safe_settlement_date(year: int, month: int, day: int) -> date:
    """Clamp February 29 to February 28 in non-leap target years."""
    return date(year, month, min(day, monthrange(year, month)[1]))


def get_current_leave_year_range(
    today: date, settlement_month: int, settlement_day: int
) -> tuple[date, date]:
    settlement = safe_settlement_date(today.year, settlement_month, settlement_day)
    if today <= settlement:
        previous = safe_settlement_date(
            today.year - 1, settlement_month, settlement_day
        )
        return previous + timedelta(days=1), settlement
    following = safe_settlement_date(today.year + 1, settlement_month, settlement_day)
    return settlement + timedelta(days=1), following


def get_current_cycle_range(
    today: date, settlement_month: int, settlement_day: int
) -> tuple[date, date]:
    """Shared annual/comp cycle helper (the settlement day closes the cycle)."""
    return get_current_leave_year_range(today, settlement_month, settlement_day)
