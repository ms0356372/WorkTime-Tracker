from datetime import date
from worktime_tracker.database.database import Database
from worktime_tracker.database.repositories import SettingsRepository
from worktime_tracker.models import DeductionPriority, TransactionType
from worktime_tracker.services.balance_service import LeaveBalanceService
from worktime_tracker.utils.leave_year import get_current_cycle_range


def cycle(start, end, total=None):
    value = {"start_date": start, "end_date": end}
    if total is not None:
        value["total_minutes"] = total
    return value


def test_settlement_then_new_grant_does_not_carry_old_balance():
    events = LeaveBalanceService().recalculate_balances(
        [], annual_opening=720, today=date(2026, 7, 5), activation_date=date(2026, 1, 1),
        annual_cycles=[cycle("2025-07-01", "2026-06-30", 4800), cycle("2026-07-01", "2027-06-30", 4800)],
    )
    settlement = next(e for e in events if e.transaction_type == TransactionType.ANNUAL_LEAVE_SETTLEMENT)
    grant = next(e for e in events if e.transaction_type == TransactionType.ANNUAL_LEAVE_GRANT)
    assert (settlement.annual_change, settlement.annual_balance) == (-720, 0)
    assert (grant.annual_change, grant.annual_balance) == (4800, 4800)


def test_positive_and_negative_comp_settle_to_zero():
    for opening in (900, -180):
        events = LeaveBalanceService().recalculate_balances(
            [], comp_opening=opening, today=date(2026, 7, 5), activation_date=date(2026, 1, 1),
            comp_cycles=[cycle("2025-07-01", "2026-06-30")],
        )
        event = next(e for e in events if e.transaction_type == TransactionType.COMP_LEAVE_SETTLEMENT)
        assert (event.comp_change, event.comp_balance) == (-opening, 0)


def test_activation_prevents_historical_settlement():
    events = LeaveBalanceService().recalculate_balances(
        [], annual_opening=720, today=date(2026, 9, 4), activation_date=date(2026, 9, 4),
        annual_cycles=[cycle("2025-07-01", "2026-06-30", 4800)],
    )
    assert not any(e.transaction_type == TransactionType.ANNUAL_LEAVE_SETTLEMENT for e in events)


def test_fresh_database_defaults_and_cycle_helper(tmp_path):
    db = Database(tmp_path / "new.sqlite3", today_provider=lambda: date(2026, 9, 4))
    settings = SettingsRepository(db)
    assert settings.deduction_priority() == DeductionPriority.ANNUAL_LEAVE_FIRST
    assert settings.get("comp_leave_settlement_date") == "2026-12-31"
    assert get_current_cycle_range(date(2026, 9, 4), 6, 30) == (date(2026, 7, 1), date(2027, 6, 30))
