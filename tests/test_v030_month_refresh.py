"""v0.3.0 month navigation and stable refresh regressions."""

from datetime import date
from worktime_tracker.database import (
    Database,
    LedgerRepository,
    SettingsRepository,
    WorkRecordRepository,
)
from worktime_tracker.models import WorkRecord
from worktime_tracker.services.record_service import WorkRecordService
from worktime_tracker.utils.months import next_month, previous_month


def test_month_arithmetic_handles_year_boundaries():
    assert previous_month(2026, 9) == (2026, 8)
    assert previous_month(2026, 1) == (2025, 12)
    assert next_month(2026, 12) == (2027, 1)


def test_records_for_month_uses_exact_date_range(tmp_path):
    repository = WorkRecordRepository(Database(tmp_path / "records.sqlite3"))
    for day in (
        date(2026, 8, 31),
        date(2026, 9, 1),
        date(2026, 9, 30),
        date(2026, 10, 1),
    ):
        repository.save(WorkRecord(day, "09:00", "18:00"))
    assert [record.work_date for record in repository.records_for_month(2026, 9)] == [
        date(2026, 9, 30),
        date(2026, 9, 1),
    ]


def test_save_update_and_delete_keep_recent_records_in_sync(tmp_path):
    db = Database(tmp_path / "records.sqlite3")
    records = WorkRecordRepository(db)
    ledger = LedgerRepository(db)
    settings = SettingsRepository(db)
    service = WorkRecordService(records, ledger, settings)
    service.save(WorkRecord(date(2026, 9, 1), "09:00", "18:00"))
    service.save(WorkRecord(date(2026, 9, 2), "09:00", "18:00"))
    service.save(WorkRecord(date(2026, 9, 1), "10:00", "18:00"))
    assert (
        len(records.all()) == 2
        and records.get_by_date(date(2026, 9, 1)).clock_in == "10:00"
    )
    assert len(records.recent(5)) == 2
    service.delete(records.get_by_date(date(2026, 9, 2)).id)
    assert [record.work_date for record in records.recent(5)] == [date(2026, 9, 1)]
