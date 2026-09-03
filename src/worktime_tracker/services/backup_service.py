"""Versioned UTF-8/ZIP backup and transaction-safe restore services."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

from worktime_tracker.config import APP_VERSION
from worktime_tracker.database.database import LATEST_SCHEMA_VERSION
from worktime_tracker.models import (
    DeductionPriority,
    LedgerEntry,
    LedgerOrigin,
    LeaveType,
    TransactionType,
    WorkRecord,
    WorkdayType,
)
from worktime_tracker.services.balance_service import LeaveBalanceService

BACKUP_FORMAT_NAME = "WorkTimeTrackerBackup"
BACKUP_FORMAT_VERSION = 1
SOURCE_TABLES = (
    "work_records",
    "settings",
    "leave_cycles",
    "monthly_settlements",
    "app_metadata",
)
TABLE_COLUMNS = {
    "work_records": {
        "id",
        "work_date",
        "clock_in",
        "clock_out",
        "break_start",
        "break_end",
        "deduct_break",
        "standard_minutes",
        "note",
        "workday_type",
        "overnight",
    },
    "settings": {"key", "value", "effective_date"},
    "leave_cycles": {"id", "start_date", "end_date", "total_minutes"},
    "monthly_settlements": {"id", "year", "month", "minutes", "rule"},
    "app_metadata": {"key", "value"},
}
REQUIRED_COLUMNS = {
    "work_records": {"id", "work_date", "clock_in", "clock_out"},
    "settings": {"key", "value"},
    "leave_cycles": {"id", "start_date", "end_date", "total_minutes"},
    "monthly_settlements": {"id", "year", "month", "minutes", "rule"},
    "app_metadata": {"key", "value"},
}
LEDGER_COLUMNS = {
    "id",
    "entry_date",
    "entry_type",
    "reason",
    "comp_change",
    "annual_change",
    "comp_balance",
    "annual_balance",
    "source_record_id",
    "transaction_datetime",
    "transaction_type",
    "ledger_origin",
    "source_leave_type",
    "target_leave_type",
    "source_minutes",
    "target_minutes",
    "note",
    "created_at",
    "reversal_of_id",
}


class BackupValidationError(ValueError):
    pass


def backup_filename(now=None, pre_restore=False):
    stamp = (now or datetime.now().astimezone()).strftime("%Y%m%d_%H%M%S")
    prefix = "工時管家_還原前備份" if pre_restore else "工時管家備份"
    return f"{prefix}_{stamp}.worktimebackup"


def _source_data(db):
    tables = {
        name: [dict(row) for row in db.connection.execute(f"SELECT * FROM {name}")]
        for name in SOURCE_TABLES
    }
    manual = [
        dict(row)
        for row in db.connection.execute(
            "SELECT * FROM balance_ledger WHERE ledger_origin=? ORDER BY transaction_datetime,id",
            (str(LedgerOrigin.MANUAL),),
        )
    ]
    return {"tables": tables, "manual_ledger_events": manual}


def create_backup(db, path, now=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _source_data(db)
    data_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    manifest = {
        "format_name": BACKUP_FORMAT_NAME,
        "backup_format_version": BACKUP_FORMAT_VERSION,
        "app_version": APP_VERSION,
        "created_at": (now or datetime.now(timezone.utc)).astimezone().isoformat(),
        "database_schema_version": LATEST_SCHEMA_VERSION,
        "record_count": len(data["tables"]["work_records"]),
        "data_sha256": hashlib.sha256(data_bytes).hexdigest(),
    }
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        archive.writestr("data.json", data_bytes)
    return path


def inspect_backup(path):
    try:
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            if not {"manifest.json", "data.json"}.issubset(names):
                raise BackupValidationError("備份缺少 manifest.json 或 data.json。")
            manifest_bytes = archive.read("manifest.json")
            data_bytes = archive.read("data.json")
    except (BadZipFile, OSError) as exc:
        raise BackupValidationError("備份不是有效的 ZIP 檔案。") from exc
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        data = json.loads(data_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupValidationError("備份包含無效的 UTF-8 JSON。") from exc
    if manifest.get("format_name") != BACKUP_FORMAT_NAME:
        raise BackupValidationError("不是工時管家備份檔。")
    if manifest.get("backup_format_version") != BACKUP_FORMAT_VERSION:
        raise BackupValidationError("不支援的備份格式版本。")
    if hashlib.sha256(data_bytes).hexdigest() != manifest.get("data_sha256"):
        raise BackupValidationError("備份資料 checksum 驗證失敗。")
    tables = data.get("tables")
    if (
        not isinstance(tables, dict)
        or not isinstance(tables.get("work_records"), list)
        or not isinstance(tables.get("settings"), list)
        or not isinstance(data.get("manual_ledger_events"), list)
    ):
        raise BackupValidationError("備份缺少必要資料欄位。")
    if manifest.get("record_count") != len(tables["work_records"]):
        raise BackupValidationError("備份紀錄數量與 manifest 不一致。")
    for table, allowed in TABLE_COLUMNS.items():
        rows = tables.get(table, [])
        if not isinstance(rows, list) or any(
            not isinstance(row, dict)
            or not REQUIRED_COLUMNS[table].issubset(row)
            or not set(row).issubset(allowed)
            for row in rows
        ):
            raise BackupValidationError(f"備份的 {table} 欄位無效。")
    if any(
        not isinstance(row, dict)
        or not {
            "id",
            "entry_date",
            "entry_type",
            "reason",
            "transaction_datetime",
            "transaction_type",
            "ledger_origin",
            "created_at",
        }.issubset(row)
        or not set(row).issubset(LEDGER_COLUMNS)
        for row in data["manual_ledger_events"]
    ):
        raise BackupValidationError("備份的手動 Ledger 欄位無效。")
    dates = [row.get("work_date") for row in tables["work_records"]]
    if None in dates or len(dates) != len(set(dates)):
        raise BackupValidationError("備份的工時日期無效或重複。")
    return manifest, data


def _insert_rows(con, table, rows):
    for row in rows:
        columns = ",".join(row)
        marks = ",".join("?" for _ in row)
        con.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({marks})", tuple(row.values())
        )


def _record(row):
    return WorkRecord(
        date.fromisoformat(row["work_date"]),
        row["clock_in"],
        row["clock_out"],
        row.get("break_start"),
        row.get("break_end"),
        bool(row.get("deduct_break", 1)),
        int(row.get("standard_minutes", 480)),
        row.get("note", ""),
        WorkdayType(row.get("workday_type", WorkdayType.NORMAL)),
        bool(row.get("overnight", 0)),
        row.get("id"),
    )


def _ledger(row):
    return LedgerEntry(
        date.fromisoformat(row["entry_date"]),
        row["entry_type"],
        row["reason"],
        int(row["comp_change"]),
        int(row["annual_change"]),
        int(row.get("comp_balance", 0)),
        int(row.get("annual_balance", 0)),
        row.get("source_record_id"),
        row.get("id"),
        datetime.fromisoformat(row["transaction_datetime"]),
        TransactionType(row["transaction_type"]),
        LedgerOrigin(row["ledger_origin"]),
        LeaveType(row["source_leave_type"]) if row.get("source_leave_type") else None,
        LeaveType(row["target_leave_type"]) if row.get("target_leave_type") else None,
        row.get("source_minutes"),
        row.get("target_minutes"),
        row.get("note", ""),
        datetime.fromisoformat(row["created_at"]),
        row.get("reversal_of_id"),
    )


def restore_backup(db, path, safety_directory=None, fault_injector=None):
    """Validate, snapshot current data, then replace sources and derived ledger atomically."""
    manifest, data = inspect_backup(path)
    safety_dir = Path(safety_directory or Path(path).parent)
    safety_path = safety_dir / backup_filename(pre_restore=True)
    create_backup(db, safety_path)
    tables = data["tables"]
    settings = {row["key"]: row["value"] for row in tables["settings"]}
    records = [_record(row) for row in tables["work_records"]]
    manual = [_ledger(row) for row in data["manual_ledger_events"]]
    priority = DeductionPriority(
        settings.get("leave_deduction_priority", DeductionPriority.COMP_TIME_FIRST)
    )
    rebuilt = LeaveBalanceService().recalculate_balances(
        records,
        annual_opening=int(settings.get("annual_leave_total_minutes", "0") or 0),
        priority=priority,
        manual_transactions=manual,
    )
    with db.transaction() as con:
        con.execute("DELETE FROM balance_ledger")
        for table in reversed(SOURCE_TABLES):
            con.execute(f"DELETE FROM {table}")
        if fault_injector:
            fault_injector()
        for table in SOURCE_TABLES:
            _insert_rows(con, table, tables.get(table, []))
        # Manual source events retain IDs so reversal relationships remain valid.
        _insert_rows(con, "balance_ledger", data["manual_ledger_events"])
        from worktime_tracker.database.repositories import LedgerRepository

        ledger_repository = LedgerRepository(db)
        for entry in rebuilt:
            if entry.ledger_origin == LedgerOrigin.MANUAL:
                con.execute(
                    "UPDATE balance_ledger SET comp_balance=?,annual_balance=? WHERE id=?",
                    (entry.comp_balance, entry.annual_balance, entry.id),
                )
            else:
                ledger_repository.add(entry, con)
    return {
        "manifest": manifest,
        "safety_backup": safety_path,
        "record_count": len(records),
    }
