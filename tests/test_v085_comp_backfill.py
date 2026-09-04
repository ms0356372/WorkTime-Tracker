from datetime import date, datetime, time

import pytest

from worktime_tracker.models import LedgerEntry, LedgerOrigin, TransactionType
from worktime_tracker.services.balance_service import LeaveBalanceService


def adjustment(day: date, minutes: int) -> LedgerEntry:
    return LedgerEntry(
        day, "手動調整", "source event", comp_change=minutes,
        transaction_datetime=datetime.combine(day, time(12)),
        transaction_type=TransactionType.ADJUSTMENT,
        ledger_origin=LedgerOrigin.MANUAL,
    )


def rebuild(minutes=48 * 60, mode="MONTHLY"):
    return LeaveBalanceService().recalculate_balances(
        [],
        manual_transactions=[adjustment(date(2026, 8, 20), minutes)],
        comp_policies=[{
            "effective_from": "2026-07-01", "mode": mode,
            "monthly_cap_minutes": 40 * 60,
            "cash_hourly_rate_cents": 25000,
        }],
        comp_cycles=[{"start_date": "2026-07-01", "end_date": "2027-06-30"}],
        current_comp_cycle_start=date(2026, 7, 1),
        today=date(2026, 9, 4),
    )


def matching(events, kind, month):
    return [e for e in events if e.transaction_type == kind and e.entry_date.month == month]


def test_august_backfill_settles_using_work_date_and_is_deterministic():
    for _ in range(10):
        events = rebuild()
        transfer = matching(events, TransactionType.COMP_MONTHLY_TRANSFER, 8)
        cash = matching(events, TransactionType.COMP_MONTHLY_CASH_SETTLEMENT, 8)
        assert len(transfer) == len(cash) == 1
        assert transfer[0].source_minutes == 40 * 60
        assert cash[0].source_minutes == 8 * 60
        assert cash[0].cash_amount_cents == 200000
        assert (cash[0].monthly_comp_balance, cash[0].annual_comp_balance) == (0, 40 * 60)


def test_historical_change_replaces_cash_result_and_current_month_is_not_settled():
    changed = rebuild(45 * 60)
    cash = matching(changed, TransactionType.COMP_MONTHLY_CASH_SETTLEMENT, 8)
    assert len(cash) == 1
    assert (cash[0].source_minutes, cash[0].cash_amount_cents) == (5 * 60, 125000)
    assert not matching(changed, TransactionType.COMP_MONTHLY_TRANSFER, 9)


def test_current_cycle_boundary_does_not_settle_previous_cycle_months():
    events = LeaveBalanceService().recalculate_balances(
        [], manual_transactions=[adjustment(date(2026, 5, 20), 48 * 60)],
        comp_policies=[{"effective_from": "2026-07-01", "mode": "MONTHLY",
                       "monthly_cap_minutes": 2400, "cash_hourly_rate_cents": 25000}],
        current_comp_cycle_start=date(2026, 7, 1), today=date(2026, 9, 4),
    )
    assert not matching(events, TransactionType.COMP_MONTHLY_TRANSFER, 5)
    assert not matching(events, TransactionType.COMP_MONTHLY_TRANSFER, 6)


def test_annual_mode_ignores_monthly_cap_and_creates_no_monthly_settlement():
    events = rebuild(80 * 60, mode="ANNUAL")
    assert events[-1].comp_balance == 80 * 60
    assert not any(e.transaction_type in {
        TransactionType.COMP_MONTHLY_TRANSFER,
        TransactionType.COMP_MONTHLY_CASH_SETTLEMENT,
    } for e in events)


def test_repository_validation_contract_is_mode_specific():
    from worktime_tracker.database.database import Database
    from worktime_tracker.database.repositories import SettingsRepository

    repo = SettingsRepository(Database(":memory:", today_provider=lambda: date(2026, 9, 4)))
    repo.set("comp_leave_settlement_date", "2027-06-30")
    repo.set_comp_policy("ANNUAL", 0, 0)
    assert repo.comp_policies()[-1]["effective_from"] == "2026-07-01"
    with pytest.raises(ValueError):
        repo.set_comp_policy("MONTHLY", 0, 0)
