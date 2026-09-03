"""Versioned backup, safe restore, corruption, and rollback regressions."""

import json
import hashlib
from datetime import date, datetime, timezone
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from worktime_tracker.database import (
    CalendarOverrideRepository,
    Database,
    LedgerRepository,
    OfficialHolidayRepository,
    SettingsRepository,
    WorkRecordRepository,
)
from worktime_tracker.models import LeaveType, WorkRecord
from worktime_tracker.services.backup_service import (
    BackupValidationError,
    create_backup,
    inspect_backup,
    restore_backup,
)
from worktime_tracker.services.leave_conversion_service import LeaveConversionService
from worktime_tracker.services.record_service import WorkRecordService


def populated_database(path):
    db = Database(path)
    records = WorkRecordRepository(db)
    settings = SettingsRepository(db)
    ledger = LedgerRepository(db)
    settings.set("annual_leave_total_minutes", "4800")
    settings.set("annual_leave_settlement_date", "2026-12-31")
    settings.set_lunch_break("12:00", "12:30")
    service = WorkRecordService(records, ledger, settings)
    for day, note in ((1, "客戶會議"), (2, "外勤"), (3, "加班")):
        service.save(WorkRecord(date(2026, 9, day), "08:00", "17:00", note=note))
    ledger.save_conversion(
        LeaveConversionService(),
        LeaveType.COMP_TIME,
        LeaveType.ANNUAL_LEAVE,
        30,
        "補休轉特休",
    )
    service.rebuild_ledger()
    return db, records, settings, ledger


def test_backup_round_trip_restores_sources_unicode_and_derived_balances(tmp_path):
    source, source_records, _, source_ledger = populated_database(
        tmp_path / "source.db"
    )
    expected_balance = source_ledger.current_balances()
    CalendarOverrideRepository(source).save(date(2026, 9, 5), "WORKDAY", "公司補班")
    OfficialHolidayRepository(source).replace_year(
        2026, [(date(2026, 10, 9), "國慶日補假")], "fixture"
    )
    backup = create_backup(
        source,
        tmp_path / "transfer.worktimebackup",
        datetime(2026, 9, 3, 10, tzinfo=timezone.utc),
    )
    manifest, data = inspect_backup(backup)
    assert manifest["format_name"] == "WorkTimeTrackerBackup"
    assert manifest["backup_format_version"] == 2
    assert manifest["record_count"] == 3
    assert len(data["manual_ledger_events"]) == 1
    with ZipFile(backup) as archive:
        assert set(archive.namelist()) == {"manifest.json", "data.json"}
        assert "客戶會議" in archive.read("data.json").decode("utf-8")

    target = Database(tmp_path / "target.db")
    result = restore_backup(target, backup, tmp_path / "safety")
    restored_records = WorkRecordRepository(target).all()
    restored_settings = SettingsRepository(target)
    restored_ledger = LedgerRepository(target)
    assert [record.note for record in restored_records] == ["客戶會議", "外勤", "加班"]
    assert restored_settings.lunch_break() == ("12:00", "12:30")
    assert restored_settings.get("annual_leave_total_minutes") == "4800"
    assert CalendarOverrideRepository(target).get(date(2026, 9, 5))["note"] == "公司補班"
    assert OfficialHolidayRepository(target).get(date(2026, 10, 9))["name"] == "國慶日補假"
    assert restored_ledger.current_balances() == expected_balance
    assert (
        len([entry for entry in restored_ledger.all() if entry.source_record_id]) == 3
    )
    assert len([entry for entry in restored_ledger.all() if entry.source_minutes]) == 1
    assert result["safety_backup"].exists()
    assert len(source_records.all()) == 3


def rewritten_backup(
    source, destination, *, remove=None, manifest_change=None, invalid_data=False
):
    with ZipFile(source) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    if remove:
        files.pop(remove)
    if manifest_change:
        manifest = json.loads(files["manifest.json"].decode("utf-8"))
        manifest.update(manifest_change)
        files["manifest.json"] = json.dumps(manifest).encode("utf-8")
    if invalid_data:
        files["data.json"] = b"{invalid"
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return destination


@pytest.mark.parametrize(
    "variant",
    [
        "bad_zip",
        "missing_manifest",
        "missing_data",
        "format",
        "version",
        "invalid_json",
    ],
)
def test_corrupted_backups_are_rejected_without_modifying_database(tmp_path, variant):
    db, records, _, _ = populated_database(tmp_path / "current.db")
    valid = create_backup(db, tmp_path / "valid.worktimebackup")
    candidate = tmp_path / f"{variant}.worktimebackup"
    if variant == "bad_zip":
        candidate.write_bytes(b"not a zip")
    elif variant == "missing_manifest":
        rewritten_backup(valid, candidate, remove="manifest.json")
    elif variant == "missing_data":
        rewritten_backup(valid, candidate, remove="data.json")
    elif variant == "format":
        rewritten_backup(valid, candidate, manifest_change={"format_name": "Wrong"})
    elif variant == "version":
        rewritten_backup(
            valid, candidate, manifest_change={"backup_format_version": 999}
        )
    else:
        rewritten_backup(valid, candidate, invalid_data=True)
    with pytest.raises(BackupValidationError):
        restore_backup(db, candidate, tmp_path / "safety")
    assert len(records.all()) == 3


def test_restore_exception_rolls_back_and_keeps_pre_restore_snapshot(tmp_path):
    db, records, _, _ = populated_database(tmp_path / "current.db")
    empty = Database(tmp_path / "empty.db")
    backup = create_backup(empty, tmp_path / "empty.worktimebackup")

    def fail_mid_restore():
        raise RuntimeError("simulated restore failure")

    with pytest.raises(RuntimeError, match="simulated"):
        restore_backup(db, backup, tmp_path / "safety", fail_mid_restore)
    assert len(records.all()) == 3
    snapshots = list((tmp_path / "safety").glob("工時管家_還原前備份_*.worktimebackup"))
    assert len(snapshots) == 1
    assert inspect_backup(snapshots[0])[0]["record_count"] == 3


def test_v1_backup_restores_with_safe_calendar_defaults(tmp_path):
    source, _, _, _ = populated_database(tmp_path / "source-v1.db")
    modern = create_backup(source, tmp_path / "modern.worktimebackup")
    with ZipFile(modern) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        data = json.loads(archive.read("data.json"))
    data["tables"].pop("calendar_overrides")
    data["tables"].pop("official_holidays")
    data["tables"]["settings"] = [
        row for row in data["tables"]["settings"]
        if row["key"] != "work_tracking_start_date"
    ]
    data_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    manifest["backup_format_version"] = 1
    manifest["data_sha256"] = hashlib.sha256(data_bytes).hexdigest()
    legacy = tmp_path / "legacy.worktimebackup"
    with ZipFile(legacy, "w", ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest).encode())
        archive.writestr("data.json", data_bytes)
    target = Database(tmp_path / "target-v1.db")
    restore_backup(target, legacy, tmp_path / "safety-v1")
    assert len(WorkRecordRepository(target).all()) == 3
    assert SettingsRepository(target).get("work_tracking_start_date") == date.today().isoformat()
    assert CalendarOverrideRepository(target).all() == []
