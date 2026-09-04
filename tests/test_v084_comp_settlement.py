from datetime import date, datetime, time

from worktime_tracker.models import LedgerEntry, LedgerOrigin, TransactionType
from worktime_tracker.services.balance_service import LeaveBalanceService


def policy(day="2026-01-01", mode="MONTHLY", cap=2400, rate=25000):
    return {"effective_from": day, "mode": mode,
            "monthly_cap_minutes": cap, "cash_hourly_rate_cents": rate}


def manual(day, minutes):
    return LedgerEntry(
        day, "手動調整", "test", comp_change=minutes,
        transaction_datetime=datetime.combine(day, time(12)),
        transaction_type=TransactionType.ADJUSTMENT,
        ledger_origin=LedgerOrigin.MANUAL,
    )


def event(events, kind, year, month):
    return next(e for e in events if e.transaction_type == kind
                and (e.entry_date.year, e.entry_date.month) == (year, month))


def test_monthly_january_february_caps_only_month_bucket_and_uses_integer_money():
    events = LeaveBalanceService().recalculate_balances(
        [], manual_transactions=[manual(date(2026, 1, 10), 48 * 60),
                                 manual(date(2026, 2, 10), 45 * 60)],
        comp_policies=[policy()], activation_date=date(2026, 1, 1),
        today=date(2026, 3, 1),
    )
    jan_cash = event(events, TransactionType.COMP_MONTHLY_CASH_SETTLEMENT, 2026, 1)
    feb_cash = event(events, TransactionType.COMP_MONTHLY_CASH_SETTLEMENT, 2026, 2)
    assert (jan_cash.source_minutes, jan_cash.cash_amount_cents,
            jan_cash.monthly_comp_balance, jan_cash.annual_comp_balance) == (480, 200000, 0, 2400)
    assert (feb_cash.source_minutes, feb_cash.cash_amount_cents,
            feb_cash.monthly_comp_balance, feb_cash.annual_comp_balance) == (300, 125000, 0, 4800)
    assert events[-1].comp_balance == 80 * 60  # annual pool is not capped at 40h


def test_comp_deduction_consumes_monthly_before_annual_and_crosses_buckets():
    entries = [manual(date(2026, 1, 1), 80 * 60),
               manual(date(2026, 3, 1), 12 * 60),
               manual(date(2026, 3, 2), -20 * 60)]
    events = LeaveBalanceService().recalculate_balances(
        [], manual_transactions=entries,
        comp_policies=[policy("2026-03-01")], today=date(2026, 3, 3),
    )
    assert (events[-1].monthly_comp_balance, events[-1].annual_comp_balance,
            events[-1].comp_balance) == (0, 72 * 60, 72 * 60)


def test_ninety_minutes_cash_uses_fractional_hour_without_float():
    events = LeaveBalanceService().recalculate_balances(
        [], manual_transactions=[manual(date(2026, 1, 5), 2490)],
        comp_policies=[policy()], today=date(2026, 2, 1),
    )
    cash = event(events, TransactionType.COMP_MONTHLY_CASH_SETTLEMENT, 2026, 1)
    assert (cash.source_minutes, cash.cash_hourly_rate_cents, cash.cash_amount_cents) == (90, 25000, 37500)


def test_midmonth_annual_cut_clears_old_monthly_and_only_new_cycle_reaches_month_end():
    events = LeaveBalanceService().recalculate_balances(
        [], comp_opening=80 * 60,
        manual_transactions=[manual(date(2026, 6, 10), 10 * 60), manual(date(2026, 6, 20), 5 * 60)],
        comp_policies=[policy()], activation_date=date(2026, 1, 1),
        comp_cycles=[{"start_date": "2025-06-16", "end_date": "2026-06-15"}],
        today=date(2026, 7, 1),
    )
    annual = event(events, TransactionType.COMP_LEAVE_SETTLEMENT, 2026, 6)
    transfer = event(events, TransactionType.COMP_MONTHLY_TRANSFER, 2026, 6)
    assert (annual.monthly_comp_balance, annual.annual_comp_balance, annual.comp_balance) == (0, 0, 0)
    assert transfer.source_minutes == 5 * 60
    assert events[-1].comp_balance == 5 * 60


def test_settlement_day_is_not_finalized_until_following_day():
    kwargs = dict(comp_opening=600, activation_date=date(2026, 1, 1),
                  comp_cycles=[{"start_date": "2025-07-01", "end_date": "2026-06-30"}])
    same_day = LeaveBalanceService().recalculate_balances([], today=date(2026, 6, 30), **kwargs)
    next_day = LeaveBalanceService().recalculate_balances([], today=date(2026, 7, 1), **kwargs)
    assert not any(e.transaction_type == TransactionType.COMP_LEAVE_SETTLEMENT for e in same_day)
    assert event(next_day, TransactionType.COMP_LEAVE_SETTLEMENT, 2026, 6).comp_balance == 0


def test_annual_to_monthly_keeps_existing_comp_in_annual_bucket():
    events = LeaveBalanceService().recalculate_balances(
        [], comp_opening=50 * 60,
        comp_policies=[policy("2026-09-15")], today=date(2026, 9, 16),
    )
    assert (events[-1].monthly_comp_balance, events[-1].annual_comp_balance) == (0, 50 * 60)


def test_monthly_to_annual_merges_buckets_without_losing_total():
    events = LeaveBalanceService().recalculate_balances(
        [], comp_opening=80 * 60,
        manual_transactions=[manual(date(2026, 3, 2), 10 * 60), manual(date(2026, 3, 16), 0)],
        comp_policies=[policy("2026-03-01"), policy("2026-03-15", "ANNUAL")],
        today=date(2026, 3, 17),
    )
    assert (events[-1].monthly_comp_balance, events[-1].annual_comp_balance,
            events[-1].comp_balance) == (0, 90 * 60, 90 * 60)
