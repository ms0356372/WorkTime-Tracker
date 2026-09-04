"""SQLite connection and forward-only transactional migrations."""
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Callable

LATEST_SCHEMA_VERSION = 4

class Database:
    def __init__(
        self,
        path: str | Path,
        today_provider: Callable[[], date] | None = None,
    ):
        self.path = str(path)
        self.today_provider = today_provider or date.today
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.migrate()

    def migrate(self) -> None:
        version = self.connection.execute("PRAGMA user_version").fetchone()[0]
        existing_install = version > 0
        if version < 1:
            self.connection.executescript("""
            CREATE TABLE work_records(id INTEGER PRIMARY KEY, work_date TEXT NOT NULL UNIQUE, clock_in TEXT, clock_out TEXT, break_start TEXT, break_end TEXT, deduct_break INTEGER NOT NULL DEFAULT 1, standard_minutes INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '', workday_type TEXT NOT NULL, overnight INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT NOT NULL, effective_date TEXT);
            CREATE TABLE leave_cycles(id INTEGER PRIMARY KEY, start_date TEXT NOT NULL, end_date TEXT NOT NULL, total_minutes INTEGER NOT NULL CHECK(total_minutes>=0));
            CREATE TABLE balance_ledger(id INTEGER PRIMARY KEY, entry_date TEXT NOT NULL, entry_type TEXT NOT NULL, reason TEXT NOT NULL, comp_change INTEGER NOT NULL, annual_change INTEGER NOT NULL, comp_balance INTEGER NOT NULL, annual_balance INTEGER NOT NULL, source_record_id INTEGER REFERENCES work_records(id));
            CREATE TABLE monthly_settlements(id INTEGER PRIMARY KEY, year INTEGER NOT NULL, month INTEGER NOT NULL, minutes INTEGER NOT NULL, rule TEXT NOT NULL, UNIQUE(year,month));
            CREATE TABLE app_metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            PRAGMA user_version=1;
            """)
            version = 1
        if version < 2:
            # Additive migration keeps every v1 row and gives it deterministic defaults.
            columns = {
                "transaction_datetime": "TEXT",
                "transaction_type": "TEXT NOT NULL DEFAULT 'WORKTIME_EARN'",
                "ledger_origin": "TEXT NOT NULL DEFAULT 'SYSTEM'",
                "source_leave_type": "TEXT",
                "target_leave_type": "TEXT",
                "source_minutes": "INTEGER",
                "target_minutes": "INTEGER",
                "note": "TEXT NOT NULL DEFAULT ''",
                "created_at": "TEXT",
                "reversal_of_id": "INTEGER REFERENCES balance_ledger(id)",
            }
            existing = {row[1] for row in self.connection.execute("PRAGMA table_info(balance_ledger)")}
            for name, definition in columns.items():
                if name not in existing:
                    self.connection.execute(f"ALTER TABLE balance_ledger ADD COLUMN {name} {definition}")
            self.connection.execute("UPDATE balance_ledger SET transaction_datetime=entry_date || 'T00:00:00' WHERE transaction_datetime IS NULL")
            self.connection.execute("UPDATE balance_ledger SET created_at=transaction_datetime WHERE created_at IS NULL")
            self.connection.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('leave_deduction_priority','COMP_TIME_FIRST')")
            self.connection.execute("PRAGMA user_version=2")
            version = 2
        if version < 3:
            # Calendar data is additive. Existing records and settings are untouched.
            self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS calendar_overrides(
                id INTEGER PRIMARY KEY,
                work_date TEXT NOT NULL UNIQUE,
                day_type TEXT NOT NULL CHECK(day_type IN ('WORKDAY','NON_WORKDAY')),
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS official_holidays(
                holiday_date TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                year INTEGER NOT NULL,
                source TEXT NOT NULL,
                synced_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_official_holidays_year
                ON official_holidays(year);
            PRAGMA user_version=3;
            """)
            self.connection.execute(
                "INSERT OR IGNORE INTO settings(key,value) VALUES('work_tracking_start_date',?)",
                (self.today_provider().isoformat(),),
            )
            version = 3
        if version < 4:
            today = self.today_provider()
            annual_value = self.connection.execute(
                "SELECT value FROM settings WHERE key='annual_leave_settlement_date'"
            ).fetchone()
            annual_settlement = annual_value[0] if annual_value else f"{today.year}-12-31"
            total_value = self.connection.execute(
                "SELECT value FROM settings WHERE key='annual_leave_total_minutes'"
            ).fetchone()
            total = int(total_value[0]) if total_value else 0
            from worktime_tracker.utils.leave_year import get_current_cycle_range
            settlement = date.fromisoformat(annual_settlement)
            cycle_start, cycle_end = get_current_cycle_range(today, settlement.month, settlement.day)
            self.connection.executescript("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_leave_cycles_range ON leave_cycles(start_date,end_date);
            CREATE TABLE IF NOT EXISTS comp_leave_cycles(
                id INTEGER PRIMARY KEY,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                UNIQUE(start_date,end_date)
            );
            """)
            self.connection.execute(
                "INSERT OR IGNORE INTO leave_cycles(start_date,end_date,total_minutes) VALUES(?,?,?)",
                (cycle_start.isoformat(), cycle_end.isoformat(), total),
            )
            self.connection.execute(
                "INSERT OR IGNORE INTO comp_leave_cycles(start_date,end_date) VALUES(?,?)",
                (cycle_start.isoformat(), cycle_end.isoformat()),
            )
            self.connection.execute(
                "INSERT OR IGNORE INTO settings(key,value) VALUES('annual_leave_settlement_date',?)",
                (annual_settlement,),
            )
            self.connection.execute(
                "INSERT OR IGNORE INTO settings(key,value) VALUES('comp_leave_settlement_date',?)",
                (annual_settlement,),
            )
            self.connection.execute(
                "INSERT OR IGNORE INTO settings(key,value) VALUES('settlement_engine_activation_date',?)",
                (today.isoformat(),),
            )
            if not existing_install:
                self.connection.execute(
                    "INSERT OR REPLACE INTO settings(key,value) VALUES('leave_deduction_priority','ANNUAL_LEAVE_FIRST')"
                )
            self.connection.execute("PRAGMA user_version=4")
        self.connection.commit()

    @contextmanager
    def transaction(self):
        try:
            yield self.connection
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def close(self) -> None: self.connection.close()
