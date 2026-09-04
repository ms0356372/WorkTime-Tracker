"""Deterministic leave ledger calculation with preserved manual transactions."""

from calendar import monthrange
from collections.abc import Iterable
from datetime import date, datetime, time, timedelta
from worktime_tracker.models import (
    DeductionPriority,
    LedgerEntry,
    LedgerOrigin,
    TransactionType,
    WorkRecord,
)
from .worktime_calculator import calculate_daily_difference, calculate_work_minutes


class LeaveBalanceService:
    def deduct_leave(
        self,
        shortfall: int,
        comp_balance: int,
        annual_balance: int = 0,
        priority: DeductionPriority = DeductionPriority.COMP_TIME_FIRST,
    ) -> tuple[int, int]:
        """Return balance changes without allowing either available balance below zero."""
        remaining = max(shortfall, 0)
        comp_change = annual_change = 0
        if priority == DeductionPriority.COMP_TIME_FIRST:
            used = min(max(comp_balance, 0), remaining)
            comp_change -= used
            remaining -= used
            used = min(max(annual_balance, 0), remaining)
            annual_change -= used
            remaining -= used
        else:
            used = min(max(annual_balance, 0), remaining)
            annual_change -= used
            remaining -= used
            used = min(max(comp_balance, 0), remaining)
            comp_change -= used
            remaining -= used
        # Preserve legacy behavior: any uncovered deficit is charged to the last leave type.
        if remaining:
            if priority == DeductionPriority.COMP_TIME_FIRST:
                annual_change -= remaining
            else:
                comp_change -= remaining
        return comp_change, annual_change

    def apply_shortfall(self, shortfall: int, comp_balance: int) -> tuple[int, int]:
        """Backward-compatible alias for the default deduction priority."""
        return self.deduct_leave(
            shortfall, comp_balance, 0, DeductionPriority.COMP_TIME_FIRST
        )

    def apply_worktime_difference(
        self,
        difference: int,
        comp_balance: int,
        annual_balance: int,
        priority: DeductionPriority,
        record: WorkRecord,
    ) -> LedgerEntry:
        if difference >= 0:
            changes = (difference, 0)
            kind = TransactionType.WORKTIME_EARN
        else:
            changes = self.deduct_leave(
                -difference, comp_balance, annual_balance, priority
            )
            kind = TransactionType.WORKTIME_DEDUCTION
        when = datetime.combine(record.work_date, time(18))
        return LedgerEntry(
            record.work_date,
            "正常工作" if difference >= 0 else "工時不足",
            "依每日工時重新計算",
            *changes,
            comp_balance + changes[0],
            annual_balance + changes[1],
            record.id,
            transaction_datetime=when,
            transaction_type=kind,
            ledger_origin=LedgerOrigin.SYSTEM,
        )

    def convert_leave(self, *args, **kwargs):
        """Delegate explicit conversions to the conversion service."""
        from .leave_conversion_service import LeaveConversionService

        return LeaveConversionService().convert_leave(*args, **kwargs)

    def reverse_conversion(self, *args, **kwargs):
        """Delegate reversals to the conversion service."""
        from .leave_conversion_service import LeaveConversionService

        return LeaveConversionService().reverse_conversion(*args, **kwargs)

    def calculate_balance(
        self,
        entries: Iterable[LedgerEntry],
        comp_opening: int = 0,
        annual_opening: int = 0,
    ) -> tuple[int, int]:
        comp, annual = comp_opening, annual_opening
        for entry in sorted(entries, key=self._sort_key):
            comp += entry.comp_change
            annual += entry.annual_change
        return comp, annual

    def recalculate_balances(
        self,
        records: Iterable[WorkRecord],
        annual_opening: int = 0,
        comp_opening: int = 0,
        monthly_cap: int | None = None,
        cap_rule: str = "提醒",
        priority: DeductionPriority = DeductionPriority.COMP_TIME_FIRST,
        manual_transactions: Iterable[LedgerEntry] = (),
        calendar=None,
        tracking_start_date: date | None = None,
        today: date | None = None,
        annual_cycles=(),
        comp_cycles=(),
        activation_date: date | None = None,
    ) -> list[LedgerEntry]:
        """Rebuild system events, retain manual audit events, then replay chronologically."""
        records = list(records)
        manual_transactions = list(manual_transactions)
        events: list[LedgerEntry] = [
            e for e in manual_transactions if e.ledger_origin == LedgerOrigin.MANUAL
        ]
        if annual_opening or comp_opening:
            years = [record.work_date.year for record in records] + [
                entry.entry_date.year for entry in manual_transactions
            ]
            opening_date = date(min(years) if years else date.today().year, 1, 1)
            events.append(
                LedgerEntry(
                    opening_date,
                    "年度期初",
                    "年度假別設定",
                    comp_opening,
                    annual_opening,
                    transaction_datetime=datetime.combine(opening_date, time.min),
                    transaction_type=TransactionType.ADJUSTMENT,
                    ledger_origin=LedgerOrigin.SYSTEM,
                )
            )
        record_by_date = {r.work_date: r for r in records}
        effective_today = today or date.today()
        activation = activation_date or effective_today
        for cycle in annual_cycles:
            start = date.fromisoformat(cycle["start_date"])
            end = date.fromisoformat(cycle["end_date"])
            total = int(cycle["total_minutes"])
            if activation <= start <= effective_today:
                events.append(LedgerEntry(
                    start, "特休年度核給", f"{start:%Y/%m/%d}～{end:%Y/%m/%d}",
                    annual_change=total,
                    transaction_datetime=datetime.combine(start, time.min),
                    transaction_type=TransactionType.ANNUAL_LEAVE_GRANT,
                    ledger_origin=LedgerOrigin.SYSTEM,
                ))
            if activation <= end <= effective_today:
                events.append(LedgerEntry(
                    end, "特休年度結算", f"結算 {start:%Y/%m/%d}～{end:%Y/%m/%d}",
                    transaction_datetime=datetime.combine(end, time(23, 59, 59)),
                    transaction_type=TransactionType.ANNUAL_LEAVE_SETTLEMENT,
                    ledger_origin=LedgerOrigin.SYSTEM,
                ))
        for cycle in comp_cycles:
            start = date.fromisoformat(cycle["start_date"])
            end = date.fromisoformat(cycle["end_date"])
            if activation <= end <= effective_today:
                events.append(LedgerEntry(
                    end, "補休年度結算", f"結算 {start:%Y/%m/%d}～{end:%Y/%m/%d}",
                    transaction_datetime=datetime.combine(end, time(23, 59, 59)),
                    transaction_type=TransactionType.COMP_LEAVE_SETTLEMENT,
                    ledger_origin=LedgerOrigin.SYSTEM,
                ))
        for record in records:
            if calendar and record.work_date > effective_today:
                continue
            standard = (
                calendar.standard_minutes_for(record.work_date)
                if calendar
                else record.standard_minutes
            )
            diff = calculate_daily_difference(
                calculate_work_minutes(record), standard
            )
            # Placeholder balance; all snapshots are rebuilt during replay below.
            event = self.apply_worktime_difference(diff, 0, 0, priority, record)
            if calendar and standard == 0 and calculate_work_minutes(record) > 0:
                event.entry_type = "假日工作"
                event.reason = calendar.day_type(record.work_date)
            events.append(event)
        if calendar and tracking_start_date and tracking_start_date < effective_today:
            for missing_day in calendar.get_missing_workdays(
                tracking_start_date, effective_today - timedelta(days=1), records
            ):
                standard = calendar.standard_minutes_for(missing_day)
                missing = WorkRecord(missing_day, standard_minutes=standard)
                event = self.apply_worktime_difference(-standard, 0, 0, priority, missing)
                event.entry_type = "未登錄工作日"
                event.reason = "正常上班日無工時紀錄"
                event.transaction_type = TransactionType.MISSING_WORKDAY_DEDUCTION
                events.append(event)
        events.sort(key=self._sort_key)
        comp = annual = 0
        rebuilt: list[LedgerEntry] = []
        current_month = None
        for event in events:
            month = (event.entry_date.year, event.entry_date.month)
            if (
                current_month
                and month != current_month
                and monthly_cap is not None
                and cap_rule in {"月結", "歸零"}
            ):
                settlement = self._settlement(current_month, comp, annual, monthly_cap)
                if settlement:
                    comp += settlement.comp_change
                    rebuilt.append(settlement)
            current_month = month
            if event.transaction_type == TransactionType.ANNUAL_LEAVE_SETTLEMENT:
                event.annual_change = -annual
            elif event.transaction_type == TransactionType.COMP_LEAVE_SETTLEMENT:
                event.comp_change = -comp
            elif event.transaction_type in {
                TransactionType.WORKTIME_DEDUCTION,
                TransactionType.MISSING_WORKDAY_DEDUCTION,
            }:
                record = record_by_date.get(event.entry_date)
                standard = (
                    calendar.standard_minutes_for(event.entry_date)
                    if calendar
                    else record.standard_minutes
                )
                diff = -standard if record is None else calculate_work_minutes(record) - standard
                source = record or WorkRecord(event.entry_date, standard_minutes=standard)
                replacement = self.apply_worktime_difference(diff, comp, annual, priority, source)
                if record is None:
                    replacement.entry_type = "未登錄工作日"
                    replacement.reason = "正常上班日無工時紀錄"
                    replacement.transaction_type = TransactionType.MISSING_WORKDAY_DEDUCTION
                event = replacement
            comp += event.comp_change
            annual += event.annual_change
            event.comp_balance = comp
            event.annual_balance = annual
            rebuilt.append(event)
        if current_month and monthly_cap is not None and cap_rule in {"月結", "歸零"}:
            settlement = self._settlement(current_month, comp, annual, monthly_cap)
            if settlement:
                rebuilt.append(settlement)
        return sorted(rebuilt, key=self._sort_key)

    def recalculate_from_date(
        self,
        records: Iterable[WorkRecord],
        from_date: date,
        manual_transactions: Iterable[LedgerEntry] = (),
        **kwargs,
    ) -> list[LedgerEntry]:
        """Recalculate from source data while retaining every manual transaction."""
        del (
            from_date
        )  # Full deterministic replay is safe and avoids partial-balance ambiguity.
        return self.recalculate_balances(
            records, manual_transactions=manual_transactions, **kwargs
        )

    @staticmethod
    def get_leave_transactions(entries: Iterable[LedgerEntry]) -> list[LedgerEntry]:
        return sorted(
            (e for e in entries if e.ledger_origin == LedgerOrigin.MANUAL),
            key=LeaveBalanceService._sort_key,
        )

    @staticmethod
    def _sort_key(entry: LedgerEntry):
        timestamp = entry.transaction_datetime or datetime.combine(
            entry.entry_date, time.min
        )
        return (
            timestamp.replace(tzinfo=None),
            entry.id or 0,
        )

    @staticmethod
    def _settlement(month, comp, annual, cap):
        excess = max(comp - cap, 0)
        if not excess:
            return None
        y, m = month
        day = date(y, m, monthrange(y, m)[1])
        return LedgerEntry(
            day,
            "月結",
            f"{y}年{m}月超過月補休上限，自動結算",
            -excess,
            0,
            comp - excess,
            annual,
            transaction_datetime=datetime.combine(day, time(23, 59)),
            transaction_type=TransactionType.MONTHLY_SETTLEMENT,
            ledger_origin=LedgerOrigin.SYSTEM,
        )
