"""v0.4.0 today-work, global lunch, and calendar-delete regressions."""

from datetime import date
from pathlib import Path
import pytest
from worktime_tracker.database import (
    Database,
    LedgerRepository,
    SettingsRepository,
    WorkRecordRepository,
)
from worktime_tracker.models import WorkRecord
from worktime_tracker.services.analytics_service import calculate_month_summary
from worktime_tracker.services.record_service import WorkRecordService
from worktime_tracker.services.worktime_calculator import (
    calculate_work_minutes,
    validate_lunch_break,
)


def make_services(tmp_path):
    db = Database(tmp_path / "records.sqlite3")
    records = WorkRecordRepository(db)
    ledger = LedgerRepository(db)
    settings = SettingsRepository(db)
    return records, ledger, settings, WorkRecordService(records, ledger, settings)


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("08:00", "17:00", 510),
        ("08:00", "11:30", 210),
        ("12:15", "17:00", 270),
        ("12:00", "12:20", 0),
        ("13:00", "17:00", 240),
    ],
)
def test_lunch_deducts_only_actual_overlap(start, end, expected):
    record = WorkRecord(
        date(2026, 9, 2), start, end, break_start="12:00", break_end="12:30"
    )
    assert calculate_work_minutes(record) == expected


def test_today_work_ignores_historical_edits(tmp_path):
    records, _, _, service = make_services(tmp_path)
    today = date(2026, 9, 2)
    service.save(WorkRecord(date(2026, 8, 31), "09:00", "18:00"))
    service.save(WorkRecord(date(2026, 9, 1), "09:00", "17:00"))
    assert service.today_work_minutes(today) == 0
    service.save(WorkRecord(date(2026, 8, 31), "08:00", "19:00"))
    assert service.today_work_minutes(today) == 0


def test_today_work_stays_today_when_old_record_changes(tmp_path):
    _, _, settings, service = make_services(tmp_path)
    settings.set_lunch_break("12:00", "12:30")
    service.save(WorkRecord(date(2026, 9, 2), "08:00", "17:00"))
    assert service.today_work_minutes(date(2026, 9, 2)) == 510
    service.save(WorkRecord(date(2026, 8, 31), "07:00", "20:00"))
    assert service.today_work_minutes(date(2026, 9, 2)) == 510


def test_changing_global_lunch_recalculates_history_ledger_and_analysis(tmp_path):
    records, ledger, settings, service = make_services(tmp_path)
    record = WorkRecord(date(2026, 9, 2), "08:00", "17:00")
    service.save(record)
    assert calculate_month_summary(records.all(), 2026, 9).work_minutes == 480
    settings.set_lunch_break("12:00", "12:30")
    service.apply_global_lunch_break()
    assert calculate_month_summary(records.all(), 2026, 9).work_minutes == 510
    assert ledger.current_balances()[0] == 30


def test_lunch_settings_persist_with_safe_defaults(tmp_path):
    db = Database(tmp_path / "settings.sqlite3")
    settings = SettingsRepository(db)
    assert settings.lunch_break() == ("12:00", "13:00")
    settings.set_lunch_break("12:00", "12:30")
    assert SettingsRepository(db).lunch_break() == ("12:00", "12:30")


def test_lunch_end_must_be_after_start():
    with pytest.raises(ValueError, match="午休結束時間必須晚於開始時間"):
        validate_lunch_break("13:00", "12:00")


def test_delete_is_calendar_only_and_android_regressions_remain():
    root = Path(__file__).parents[1]
    records = (root / "src/worktime_tracker/views/records_view.py").read_text(
        encoding="utf-8"
    )
    monthly = (root / "src/worktime_tracker/views/monthly_records_view.py").read_text(
        encoding="utf-8"
    )
    config = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "刪除此紀錄" not in records and "已計入補休" not in records
    assert 'toga.Button(\n                    "刪除"' in monthly
    assert "確認刪除紀錄" in monthly
    assert "com.google.android.material:material:1.12.0" in config
