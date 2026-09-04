"""Daily record orchestration with deterministic ledger rebuilding."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from worktime_tracker.models import WorkRecord
from worktime_tracker.database.repositories import CalendarOverrideRepository, OfficialHolidayRepository
from .balance_service import LeaveBalanceService
from .worktime_calculator import calculate_daily_difference, calculate_work_minutes


@dataclass(frozen=True)
class RecordResult:
    record: WorkRecord
    work_minutes: int
    overtime_minutes: int
    shortfall_minutes: int


class WorkRecordService:
    def __init__(self, records, ledger, settings, calendar=None, today_provider=date.today):
        self.records = records
        self.ledger = ledger
        self.settings = settings
        self.balances = LeaveBalanceService()
        if calendar is None:
            from .work_calendar_service import WorkCalendarService
            if hasattr(records, "db"):
                calendar = WorkCalendarService(
                    CalendarOverrideRepository(records.db),
                    OfficialHolidayRepository(records.db),
                    settings,
                )
            else:
                class BasicCalendar:
                    def standard_minutes_for(self, day):
                        return int(settings.get("daily_standard_minutes", "480") or 480)

                calendar = BasicCalendar()
        self.calendar = calendar
        self.today_provider = today_provider

    def save(self, record: WorkRecord) -> RecordResult:
        record.break_start, record.break_end = self.settings.lunch_break()
        actual = calculate_work_minutes(record)
        existing = self.records.get_by_date(record.work_date)
        record.id = existing.id if existing else None
        self.records.save(record)
        self.rebuild_ledger()
        difference = calculate_daily_difference(actual, self.calendar.standard_minutes_for(record.work_date))
        return RecordResult(record, actual, max(difference, 0), max(-difference, 0))

    def update(self, record: WorkRecord) -> RecordResult:
        """Update an existing record by ID and deterministically rebuild balances."""
        if record.id is None:
            raise ValueError("更新工時紀錄時必須提供 record ID。")
        existing = self.records.get_by_id(record.id)
        if existing is None:
            raise ValueError("找不到要更新的工時紀錄。")
        record.work_date = existing.work_date
        record.break_start, record.break_end = self.settings.lunch_break()
        actual = calculate_work_minutes(record)
        self.records.update(record)
        self.rebuild_ledger()
        difference = calculate_daily_difference(actual, self.calendar.standard_minutes_for(record.work_date))
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
        from worktime_tracker.database.repositories import LeaveCycleRepository
        from worktime_tracker.utils.leave_year import get_current_cycle_range

        today = self.today_provider()
        cycles = LeaveCycleRepository(self.records.db)
        annual_setting = date.fromisoformat(
            self.settings.get("annual_leave_settlement_date", f"{today.year}-12-31")
        )
        annual_start, annual_end = get_current_cycle_range(
            today, annual_setting.month, annual_setting.day
        )
        cycles.ensure_annual(annual_start, annual_end, opening)
        comp_setting = date.fromisoformat(
            self.settings.get("comp_leave_settlement_date", annual_setting.isoformat())
        )
        comp_start, comp_end = get_current_cycle_range(
            today, comp_setting.month, comp_setting.day
        )
        cycles.ensure_comp(comp_start, comp_end)
        activation_date = date.fromisoformat(self.settings.get(
            "settlement_engine_activation_date", today.isoformat()
        ))
        # A cycle that began before activation is the migration-safe legacy opening.
        # If activation is exactly the cycle start, its explicit grant is authoritative.
        legacy_opening = opening if annual_start < activation_date else 0
        kwargs = {}
        if hasattr(self.settings, "tracking_start_date") and hasattr(
            self.calendar, "get_missing_workdays"
        ):
            kwargs = {
                "calendar": self.calendar,
                "tracking_start_date": self.settings.tracking_start_date(
                    self.today_provider()
                ),
                "today": today,
            }
        kwargs.update({
            "annual_cycles": cycles.annual_all(),
            "comp_cycles": cycles.comp_all(),
            "activation_date": activation_date,
        })
        return self.ledger.rebuild_for_records(
            self.balances,
            self.records.all(),
            legacy_opening,
            self.settings.deduction_priority(),
            **kwargs,
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
