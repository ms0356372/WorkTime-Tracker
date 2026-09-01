"""SQLite connection and forward-only transactional migrations."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

LATEST_SCHEMA_VERSION = 2

class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.migrate()

    def migrate(self) -> None:
        version = self.connection.execute("PRAGMA user_version").fetchone()[0]
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
