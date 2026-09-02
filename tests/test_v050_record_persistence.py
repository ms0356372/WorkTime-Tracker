"""v0.5.0 date-authoritative WorkRecord persistence regressions."""

from datetime import date
from pathlib import Path
from worktime_tracker.database import (
    Database,
    LedgerRepository,
    SettingsRepository,
    WorkRecordRepository,
)
from worktime_tracker.models import WorkRecord
from worktime_tracker.services.analytics_service import calculate_month_summary
from worktime_tracker.services.record_service import WorkRecordService


def setup(tmp_path):
    db = Database(tmp_path / "records.sqlite3")
    records = WorkRecordRepository(db)
    ledger = LedgerRepository(db)
    settings = SettingsRepository(db)
    return db, records, ledger, WorkRecordService(records, ledger, settings)


def save(service, day, start="09:00", end="18:00", record_id=None):
    return service.save(WorkRecord(day, start, end, id=record_id)).record


def test_different_dates_are_inserted_and_permanently_coexist(tmp_path):
    _, records, _, service = setup(tmp_path)
    days = [date(2026, 8, 31), date(2026, 9, 1), date(2026, 9, 2)]
    for day in days:
        save(service, day)
    assert [record.work_date for record in records.all()] == days
    assert all(records.exists_by_date(day) for day in days)


def test_stale_editing_id_cannot_overwrite_a_different_date(tmp_path):
    _, records, _, service = setup(tmp_path)
    first = save(service, date(2026, 9, 1), "07:00", "17:00")
    save(service, date(2026, 9, 2), "08:00", "18:00", record_id=first.id)
    assert len(records.all()) == 2
    assert records.get_by_date(date(2026, 9, 1)).clock_in == "07:00"
    assert records.get_by_date(date(2026, 9, 2)).clock_in == "08:00"


def test_same_date_updates_only_that_row(tmp_path):
    _, records, _, service = setup(tmp_path)
    save(service, date(2026, 8, 31))
    save(service, date(2026, 9, 1), "07:00", "17:00")
    save(service, date(2026, 9, 2))
    save(service, date(2026, 9, 1), "08:00", "18:00")
    assert len(records.all()) == 3
    assert records.get_by_date(date(2026, 8, 31)).clock_in == "09:00"
    assert records.get_by_date(date(2026, 9, 1)).clock_in == "08:00"
    assert records.get_by_date(date(2026, 9, 2)).clock_in == "09:00"


def test_delete_removes_only_the_selected_date(tmp_path):
    _, records, _, service = setup(tmp_path)
    for day in (date(2026, 8, 31), date(2026, 9, 1), date(2026, 9, 2)):
        save(service, day)
    service.delete(records.get_by_date(date(2026, 9, 1)).id)
    assert [record.work_date for record in records.all()] == [
        date(2026, 8, 31),
        date(2026, 9, 2),
    ]


def test_month_query_and_analysis_include_every_date(tmp_path):
    _, records, _, service = setup(tmp_path)
    for day in (
        date(2026, 8, 31),
        date(2026, 9, 1),
        date(2026, 9, 2),
        date(2026, 9, 3),
    ):
        save(service, day)
    september = records.records_for_month(2026, 9)
    summary = calculate_month_summary(records.all(), 2026, 9)
    assert len(september) == 3 and summary.workdays == 3
    assert [record.work_date for record in records.recent(5)] == [
        date(2026, 9, 3),
        date(2026, 9, 2),
        date(2026, 9, 1),
        date(2026, 8, 31),
    ]


def test_same_date_update_rebuilds_instead_of_accumulating_ledger(tmp_path):
    _, records, ledger, service = setup(tmp_path)
    save(service, date(2026, 9, 1), "09:00", "20:00")
    assert ledger.current_balances()[0] == 120
    save(service, date(2026, 9, 1), "09:00", "19:00")
    assert len(records.all()) == 1 and ledger.current_balances()[0] == 60
    assert len([entry for entry in ledger.all() if entry.source_record_id]) == 1


def test_schema_and_repository_sql_are_date_scoped(tmp_path):
    db, _, _, _ = setup(tmp_path)
    indexes = db.connection.execute("PRAGMA index_list(work_records)").fetchall()
    assert any(row[2] for row in indexes)
    source = (
        Path(__file__).parents[1] / "src/worktime_tracker/database/repositories.py"
    ).read_text(encoding="utf-8")
    assert "UPDATE work_records SET" in source and "WHERE work_date=?" in source
    assert "DELETE FROM work_records WHERE id=?" in source
