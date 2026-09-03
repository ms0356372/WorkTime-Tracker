"""Settlement-date leave-year boundary regressions."""

from datetime import date

from worktime_tracker.utils.leave_year import get_current_leave_year_range


def test_leave_year_after_june_settlement():
    assert get_current_leave_year_range(date(2026, 9, 3), 6, 30) == (
        date(2026, 7, 1),
        date(2027, 6, 30),
    )


def test_leave_year_before_june_settlement():
    assert get_current_leave_year_range(date(2026, 3, 10), 6, 30) == (
        date(2025, 7, 1),
        date(2026, 6, 30),
    )


def test_calendar_year_settlement_boundaries():
    assert get_current_leave_year_range(date(2026, 12, 31), 12, 31) == (
        date(2026, 1, 1),
        date(2026, 12, 31),
    )
    assert get_current_leave_year_range(date(2027, 1, 1), 12, 31) == (
        date(2027, 1, 1),
        date(2027, 12, 31),
    )


def test_february_29_clamps_in_non_leap_years():
    assert get_current_leave_year_range(date(2025, 3, 1), 2, 29) == (
        date(2025, 3, 1),
        date(2026, 2, 28),
    )
