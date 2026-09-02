"""Daily record orchestration with deterministic ledger rebuilding."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from worktime_tracker.models import WorkRecord
from .balance_service import LeaveBalanceService
from .worktime_calculator import calculate_daily_difference, calculate_work_minutes


@dataclass(frozen=True)
class RecordResult:
    record: WorkRecord
    work_minutes: int
    overtime_minutes: int
    shortfall_minutes: int


class WorkRecordService:
    def __init__(self, records, ledger, settings):
        self.records = records
        self.ledger = ledger
        self.settings = settings
        self.balances = LeaveBalanceService()

    def save(self, record: WorkRecord) -> RecordResult:
        record.break_start, record.break_end = self.settings.lunch_break()
        actual = calculate_work_minutes(record)
        existing = self.records.get_by_date(record.work_date)
        if existing:
            record.id = existing.id
        self.records.save(record)
        self.rebuild_ledger()
        difference = calculate_daily_difference(actual, record.standard_minutes)
        return RecordResult(record, actual, max(difference, 0), max(-difference, 0))

    def delete(self, record_id: int) -> None:
        with self.records.db.transaction() as con:
            con.execute(
                "DELETE FROM balance_ledger WHERE source_record_id=?", (record_id,)
            )
            con.execute("DELETE FROM work_records WHERE id=?", (record_id,))
        self.rebuild_ledger()

    def rebuild_ledger(self):
        opening = int(self.settings.get("annual_leave_total_minutes", "0") or 0)
        return self.ledger.rebuild_for_records(
            self.balances,
            self.records.all(),
            opening,
            self.settings.deduction_priority(),
        )

    def apply_global_lunch_break(self) -> None:
        start, end = self.settings.lunch_break()
        with self.records.db.transaction() as con:
            con.execute(
                "UPDATE work_records SET break_start=?,break_end=?,deduct_break=1",
                (start, end),
            )
        self.rebuild_ledger()

    def today_work_minutes(self, today: date | None = None) -> int:
        record = self.records.get_by_date(today or date.today())
        return calculate_work_minutes(record) if record else 0
