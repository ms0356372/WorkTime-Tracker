"""Deterministic leave ledger calculation with preserved manual transactions."""
from calendar import monthrange
from collections.abc import Iterable
from datetime import date, datetime, time
from worktime_tracker.models import (DeductionPriority, LedgerEntry, LedgerOrigin,
                                     TransactionType, WorkRecord)
from .worktime_calculator import calculate_daily_difference, calculate_work_minutes

class LeaveBalanceService:
    def deduct_leave(self, shortfall: int, comp_balance: int, annual_balance: int = 0,
                     priority: DeductionPriority = DeductionPriority.COMP_TIME_FIRST) -> tuple[int, int]:
        """Return balance changes without allowing either available balance below zero."""
        remaining = max(shortfall, 0)
        comp_change = annual_change = 0
        if priority == DeductionPriority.COMP_TIME_FIRST:
            used = min(max(comp_balance, 0), remaining); comp_change -= used; remaining -= used
            used = min(max(annual_balance, 0), remaining); annual_change -= used; remaining -= used
        else:
            used = min(max(annual_balance, 0), remaining); annual_change -= used; remaining -= used
            used = min(max(comp_balance, 0), remaining); comp_change -= used; remaining -= used
        # Preserve legacy behavior: any uncovered deficit is charged to the last leave type.
        if remaining:
            if priority == DeductionPriority.COMP_TIME_FIRST: annual_change -= remaining
            else: comp_change -= remaining
        return comp_change, annual_change

    def apply_shortfall(self, shortfall: int, comp_balance: int) -> tuple[int, int]:
        """Backward-compatible alias for the default deduction priority."""
        return self.deduct_leave(shortfall, comp_balance, 0, DeductionPriority.COMP_TIME_FIRST)

    def apply_worktime_difference(self, difference: int, comp_balance: int,
                                  annual_balance: int, priority: DeductionPriority,
                                  record: WorkRecord) -> LedgerEntry:
        if difference >= 0:
            changes = (difference, 0); kind = TransactionType.WORKTIME_EARN
        else:
            changes = self.deduct_leave(-difference, comp_balance, annual_balance, priority)
            kind = TransactionType.WORKTIME_DEDUCTION
        when = datetime.combine(record.work_date, time(18))
        return LedgerEntry(record.work_date, "正常工作" if difference >= 0 else "工時不足",
                           "依每日工時重新計算", *changes,
                           comp_balance + changes[0], annual_balance + changes[1], record.id,
                           transaction_datetime=when, transaction_type=kind,
                           ledger_origin=LedgerOrigin.SYSTEM)

    def convert_leave(self, *args, **kwargs):
        """Delegate explicit conversions to the conversion service."""
        from .leave_conversion_service import LeaveConversionService
        return LeaveConversionService().convert_leave(*args, **kwargs)

    def reverse_conversion(self, *args, **kwargs):
        """Delegate reversals to the conversion service."""
        from .leave_conversion_service import LeaveConversionService
        return LeaveConversionService().reverse_conversion(*args, **kwargs)

    def calculate_balance(self, entries: Iterable[LedgerEntry], comp_opening: int = 0,
                          annual_opening: int = 0) -> tuple[int, int]:
        comp, annual = comp_opening, annual_opening
        for entry in sorted(entries, key=self._sort_key):
            comp += entry.comp_change; annual += entry.annual_change
        return comp, annual

    def recalculate_balances(self, records: Iterable[WorkRecord], annual_opening: int = 0,
                             comp_opening: int = 0, monthly_cap: int | None = None,
                             cap_rule: str = "提醒",
                             priority: DeductionPriority = DeductionPriority.COMP_TIME_FIRST,
                             manual_transactions: Iterable[LedgerEntry] = ()) -> list[LedgerEntry]:
        """Rebuild system events, retain manual audit events, then replay chronologically."""
        records = list(records)
        events: list[LedgerEntry] = [e for e in manual_transactions if e.ledger_origin == LedgerOrigin.MANUAL]
        record_by_date = {r.work_date: r for r in records}
        for record in records:
            diff = calculate_daily_difference(calculate_work_minutes(record), record.standard_minutes)
            # Placeholder balance; all snapshots are rebuilt during replay below.
            events.append(self.apply_worktime_difference(diff, 0, 0, priority, record))
        events.sort(key=self._sort_key)
        comp, annual = comp_opening, annual_opening
        rebuilt: list[LedgerEntry] = []
        current_month = None
        for event in events:
            month = (event.entry_date.year, event.entry_date.month)
            if current_month and month != current_month and monthly_cap is not None and cap_rule in {"月結", "歸零"}:
                settlement = self._settlement(current_month, comp, annual, monthly_cap)
                if settlement:
                    comp += settlement.comp_change; rebuilt.append(settlement)
            current_month = month
            if event.transaction_type == TransactionType.WORKTIME_DEDUCTION:
                record = record_by_date[event.entry_date]
                diff = calculate_daily_difference(calculate_work_minutes(record), record.standard_minutes)
                event = self.apply_worktime_difference(diff, comp, annual, priority, record)
            comp += event.comp_change; annual += event.annual_change
            event.comp_balance = comp; event.annual_balance = annual
            rebuilt.append(event)
        if current_month and monthly_cap is not None and cap_rule in {"月結", "歸零"}:
            settlement = self._settlement(current_month, comp, annual, monthly_cap)
            if settlement: rebuilt.append(settlement)
        return sorted(rebuilt, key=self._sort_key)

    def recalculate_from_date(self, records: Iterable[WorkRecord], from_date: date,
                              manual_transactions: Iterable[LedgerEntry] = (), **kwargs) -> list[LedgerEntry]:
        """Recalculate from source data while retaining every manual transaction."""
        del from_date  # Full deterministic replay is safe and avoids partial-balance ambiguity.
        return self.recalculate_balances(records, manual_transactions=manual_transactions, **kwargs)

    @staticmethod
    def get_leave_transactions(entries: Iterable[LedgerEntry]) -> list[LedgerEntry]:
        return sorted((e for e in entries if e.ledger_origin == LedgerOrigin.MANUAL), key=LeaveBalanceService._sort_key)

    @staticmethod
    def _sort_key(entry: LedgerEntry):
        return (entry.transaction_datetime or datetime.combine(entry.entry_date, time.min), entry.id or 0)

    @staticmethod
    def _settlement(month, comp, annual, cap):
        excess = max(comp-cap, 0)
        if not excess: return None
        y, m = month; day = date(y, m, monthrange(y, m)[1])
        return LedgerEntry(day, "月結", f"{y}年{m}月超過月補休上限，自動結算", -excess, 0,
                           comp-excess, annual, transaction_datetime=datetime.combine(day,time(23,59)),
                           transaction_type=TransactionType.MONTHLY_SETTLEMENT,
                           ledger_origin=LedgerOrigin.SYSTEM)
