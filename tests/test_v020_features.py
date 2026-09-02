from datetime import date
from pathlib import Path
import tomllib
from worktime_tracker.database import (
    Database,
    LedgerRepository,
    SettingsRepository,
    WorkRecordRepository,
)
from worktime_tracker.models import LeaveType, WorkRecord
from worktime_tracker.services.analytics_service import (
    calculate_month_summary,
    calculate_year_summary,
)
from worktime_tracker.services.leave_conversion_service import LeaveConversionService
from worktime_tracker.services.record_service import WorkRecordService
from worktime_tracker.services.worktime_calculator import calculate_work_minutes
from worktime_tracker.utils.formatting import format_minutes


def services(tmp_path):
    db = Database(tmp_path / "worktime.sqlite3")
    records = WorkRecordRepository(db)
    ledger = LedgerRepository(db)
    settings = SettingsRepository(db)
    settings.set("annual_leave_total_minutes", "4800")
    return db, records, ledger, settings, WorkRecordService(records, ledger, settings)


def test_workday_and_lunch_are_integer_minutes():
    record = WorkRecord(
        date(2026, 9, 2), "08:00", "17:30", break_start="12:00", break_end="13:00"
    )
    assert calculate_work_minutes(record) == 510
    assert format_minutes(510) == "8 小時 30 分"


def test_save_upserts_one_record_per_date_and_recalculates_ledger(tmp_path):
    _, records, ledger, _, service = services(tmp_path)
    first = service.save(WorkRecord(date(2026, 9, 2), "08:00", "17:30"))
    assert first.overtime_minutes == 30 and ledger.current_balances() == (30, 4800)
    updated = service.save(WorkRecord(date(2026, 9, 2), "08:00", "17:00"))
    assert len(records.all()) == 1 and updated.work_minutes == 480
    assert ledger.current_balances() == (0, 4800)


def test_shortfall_uses_priority_without_duplicate_events(tmp_path):
    _, records, ledger, _, service = services(tmp_path)
    result = service.save(WorkRecord(date(2026, 9, 2), "08:00", "16:30"))
    assert result.shortfall_minutes == 30 and ledger.current_balances() == (0, 4770)
    service.save(WorkRecord(date(2026, 9, 2), "08:00", "16:00"))
    assert ledger.current_balances() == (0, 4740)
    assert len([entry for entry in ledger.all() if entry.source_record_id]) == 1


def test_annual_leave_and_settlement_settings_persist(tmp_path):
    db, _, ledger, settings, service = services(tmp_path)
    settings.set("annual_leave_settlement_date", "2026-12-31")
    service.rebuild_ledger()
    assert SettingsRepository(db).get("annual_leave_total_minutes") == "4800"
    assert SettingsRepository(db).get("annual_leave_settlement_date") == "2026-12-31"
    assert ledger.current_balances() == (0, 4800)


def test_conversion_survives_record_recalculation(tmp_path):
    _, records, ledger, _, service = services(tmp_path)
    service.rebuild_ledger()
    conversion = LeaveConversionService()
    ledger.save_conversion(conversion, LeaveType.ANNUAL_LEAVE, LeaveType.COMP_TIME, 120)
    service.save(WorkRecord(date(2026, 9, 2), "08:00", "17:00"))
    assert ledger.current_balances() == (120, 4680)


def test_delete_rolls_back_record_ledger_effect(tmp_path):
    _, records, ledger, _, service = services(tmp_path)
    result = service.save(WorkRecord(date(2026, 9, 2), "08:00", "17:30"))
    service.delete(result.record.id)
    assert records.all() == [] and ledger.current_balances() == (0, 4800)


def test_month_and_year_analysis_separate_overtime_and_shortfall():
    rows = [
        WorkRecord(date(2026, 9, 1), "08:00", "17:30"),
        WorkRecord(date(2026, 9, 2), "08:00", "16:30"),
        WorkRecord(date(2026, 8, 31), "08:00", "17:00"),
    ]
    month = calculate_month_summary(rows, 2026, 9)
    year = calculate_year_summary(rows, 2026)
    assert (month.work_minutes, month.workdays, month.average_minutes) == (960, 2, 480)
    assert (month.overtime_minutes, month.shortfall_minutes) == (30, 30)
    assert (year.work_minutes, year.workdays) == (1440, 3)


def test_v020_metadata_and_android_regressions():
    root = Path(__file__).parents[1]
    with (root / "pyproject.toml").open("rb") as config_file:
        config = tomllib.load(config_file)
    app = config["tool"]["briefcase"]["app"]["worktime_tracker"]
    source = (root / "src/worktime_tracker/app.py").read_text(encoding="utf-8")
    dashboard = (root / "src/worktime_tracker/views/dashboard_view.py").read_text(
        encoding="utf-8"
    )
    readme = (root / "README.md").read_text(encoding="utf-8")
    metadata = (root / "src/worktime_tracker/config.py").read_text(encoding="utf-8")
    assert (
        config["project"]["version"]
        == config["tool"]["briefcase"]["version"]
        == "0.3.0"
    )
    assert (
        "com.google.android.material:material:1.12.0"
        in app["android"]["build_gradle_dependencies"]
    )
    assert "tabs.content" not in source and "content=[" in source.replace(" ", "")
    assert "疲累" not in dashboard
    assert 'NAVIGATION_UNSELECTED_COLOR = "#B0BEC5"' in source
    assert all(
        label in dashboard for label in ("今天工時", "本月工時", "目前補休", "剩餘特休")
    )
    assert not {"numpy", "pandas", "matplotlib", "scipy"}.intersection(
        config["project"]["dependencies"]
    )
    assert app["formal_name"] == "工時管家"
    assert "工時管家" in readme
    assert 'APP_NAME = "工時管家"' in metadata
