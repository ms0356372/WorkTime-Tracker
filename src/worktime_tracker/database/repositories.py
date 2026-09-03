"""Persistence repositories with immediate transactional writes."""

from datetime import date, datetime, timezone
from worktime_tracker.models import (
    DeductionPriority,
    LedgerEntry,
    LedgerOrigin,
    LeaveType,
    TransactionType,
    WorkRecord,
    WorkdayType,
)


class WorkRecordRepository:
    def __init__(self, db):
        self.db = db

    def save(self, r: WorkRecord) -> int:
        values = (
            r.work_date.isoformat(),
            r.clock_in,
            r.clock_out,
            r.break_start,
            r.break_end,
            int(r.deduct_break),
            r.standard_minutes,
            r.note,
            str(r.workday_type),
            int(r.overnight),
        )
        with self.db.transaction() as con:
            existing = con.execute(
                "SELECT id FROM work_records WHERE work_date=?",
                (r.work_date.isoformat(),),
            ).fetchone()
            if existing:
                r.id = existing[0]
                con.execute(
                    "UPDATE work_records SET clock_in=?,clock_out=?,break_start=?,break_end=?,deduct_break=?,standard_minutes=?,note=?,workday_type=?,overnight=? WHERE work_date=?",
                    values[1:] + (r.work_date.isoformat(),),
                )
                return r.id
            r.id = None
            cur = con.execute(
                "INSERT INTO work_records(work_date,clock_in,clock_out,break_start,break_end,deduct_break,standard_minutes,note,workday_type,overnight) VALUES(?,?,?,?,?,?,?,?,?,?)",
                values,
            )
            r.id = cur.lastrowid
            return r.id

    def all(self):
        return [
            WorkRecord(
                date.fromisoformat(x["work_date"]),
                x["clock_in"],
                x["clock_out"],
                x["break_start"],
                x["break_end"],
                bool(x["deduct_break"]),
                x["standard_minutes"],
                x["note"],
                WorkdayType(x["workday_type"]),
                bool(x["overnight"]),
                x["id"],
            )
            for x in self.db.connection.execute(
                "SELECT * FROM work_records ORDER BY work_date"
            )
        ]

    def get_by_date(self, work_date: date):
        row = self.db.connection.execute(
            "SELECT * FROM work_records WHERE work_date=?", (work_date.isoformat(),)
        ).fetchone()
        return self._map_record(row) if row else None

    def get_by_id(self, record_id: int):
        row = self.db.connection.execute(
            "SELECT * FROM work_records WHERE id=?", (record_id,)
        ).fetchone()
        return self._map_record(row) if row else None

    def update(self, record: WorkRecord) -> None:
        """Update one existing record by identity without changing its date."""
        if record.id is None:
            raise ValueError("更新工時紀錄時必須提供 record ID。")
        with self.db.transaction() as con:
            cursor = con.execute(
                "UPDATE work_records SET clock_in=?,clock_out=?,break_start=?,break_end=?,deduct_break=?,standard_minutes=?,note=?,workday_type=?,overnight=? WHERE id=?",
                (
                    record.clock_in,
                    record.clock_out,
                    record.break_start,
                    record.break_end,
                    int(record.deduct_break),
                    record.standard_minutes,
                    record.note,
                    str(record.workday_type),
                    int(record.overnight),
                    record.id,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("找不到要更新的工時紀錄。")

    def exists_by_date(self, work_date: date) -> bool:
        return (
            self.db.connection.execute(
                "SELECT 1 FROM work_records WHERE work_date=?", (work_date.isoformat(),)
            ).fetchone()
            is not None
        )

    def recent(self, limit: int = 7):
        return list(reversed(self.all()))[:limit]

    def records_for_month(self, year: int, month: int):
        from worktime_tracker.utils.months import next_month

        next_year, next_month_value = next_month(year, month)
        start = date(year, month, 1).isoformat()
        end = date(next_year, next_month_value, 1).isoformat()
        rows = self.db.connection.execute(
            "SELECT * FROM work_records WHERE work_date>=? AND work_date<? ORDER BY work_date DESC",
            (start, end),
        )
        return [self._map_record(row) for row in rows]

    def for_month(self, year: int, month: int):
        """Backward-compatible alias for the range-query implementation."""
        return self.records_for_month(year, month)

    @staticmethod
    def _map_record(x):
        return WorkRecord(
            date.fromisoformat(x["work_date"]),
            x["clock_in"],
            x["clock_out"],
            x["break_start"],
            x["break_end"],
            bool(x["deduct_break"]),
            x["standard_minutes"],
            x["note"],
            WorkdayType(x["workday_type"]),
            bool(x["overnight"]),
            x["id"],
        )

    def delete(self, record_id: int):
        with self.db.transaction() as con:
            con.execute("DELETE FROM work_records WHERE id=?", (record_id,))


class SettingsRepository:
    def __init__(self, db):
        self.db = db

    def get(self, key: str, default: str | None = None) -> str | None:
        row = self.db.connection.execute(
            "SELECT value FROM settings WHERE key=?", (key,)
        ).fetchone()
        return row[0] if row else default

    def set(self, key: str, value: str) -> None:
        with self.db.transaction() as con:
            con.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def deduction_priority(self) -> DeductionPriority:
        return DeductionPriority(
            self.get("leave_deduction_priority", DeductionPriority.COMP_TIME_FIRST)
        )

    def lunch_break(self) -> tuple[str, str]:
        return (
            self.get("lunch_break_start", "12:00") or "12:00",
            self.get("lunch_break_end", "13:00") or "13:00",
        )

    def set_lunch_break(self, start: str, end: str) -> None:
        with self.db.transaction() as con:
            con.execute(
                "INSERT INTO settings(key,value) VALUES('lunch_break_start',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (start,),
            )
            con.execute(
                "INSERT INTO settings(key,value) VALUES('lunch_break_end',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (end,),
            )

    def tracking_start_date(self, today: date | None = None) -> date:
        """Return a migration-safe start date, initializing it without backdating."""
        value = self.get("work_tracking_start_date")
        if value:
            return date.fromisoformat(value)
        start = today or date.today()
        self.set("work_tracking_start_date", start.isoformat())
        return start


class CalendarOverrideRepository:
    def __init__(self, db):
        self.db = db

    def get(self, day: date):
        return self.db.connection.execute(
            "SELECT * FROM calendar_overrides WHERE work_date=?", (day.isoformat(),)
        ).fetchone()

    def all(self):
        return list(self.db.connection.execute(
            "SELECT * FROM calendar_overrides ORDER BY work_date DESC"
        ))

    def save(self, day: date, day_type: str, note: str = "") -> None:
        if day_type not in {"WORKDAY", "NON_WORKDAY"}:
            raise ValueError("特殊日期類型無效。")
        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as con:
            con.execute(
                "INSERT INTO calendar_overrides(work_date,day_type,note,created_at,updated_at) "
                "VALUES(?,?,?,?,?) ON CONFLICT(work_date) DO UPDATE SET "
                "day_type=excluded.day_type,note=excluded.note,updated_at=excluded.updated_at",
                (day.isoformat(), day_type, note, now, now),
            )

    def delete(self, day: date) -> None:
        with self.db.transaction() as con:
            con.execute("DELETE FROM calendar_overrides WHERE work_date=?", (day.isoformat(),))


class OfficialHolidayRepository:
    def __init__(self, db):
        self.db = db

    def get(self, day: date):
        return self.db.connection.execute(
            "SELECT * FROM official_holidays WHERE holiday_date=?", (day.isoformat(),)
        ).fetchone()

    def for_year(self, year: int):
        return list(self.db.connection.execute(
            "SELECT * FROM official_holidays WHERE year=? ORDER BY holiday_date", (year,)
        ))

    def replace_year(self, year: int, holidays, source: str, synced_at=None) -> None:
        stamp = (synced_at or datetime.now(timezone.utc)).isoformat()
        with self.db.transaction() as con:
            con.execute("DELETE FROM official_holidays WHERE year=?", (year,))
            con.executemany(
                "INSERT INTO official_holidays(holiday_date,name,year,source,synced_at) VALUES(?,?,?,?,?)",
                [(day.isoformat(), name, year, source, stamp) for day, name in holidays],
            )

    def status(self):
        return list(self.db.connection.execute(
            "SELECT year,COUNT(*) AS holiday_count,MAX(synced_at) AS synced_at "
            "FROM official_holidays GROUP BY year ORDER BY year"
        ))


class LedgerRepository:
    def __init__(self, db):
        self.db = db

    def add(self, entry: LedgerEntry, connection=None) -> int:
        con = connection or self.db.connection
        values = (
            entry.entry_date.isoformat(),
            entry.entry_type,
            entry.reason,
            entry.comp_change,
            entry.annual_change,
            entry.comp_balance,
            entry.annual_balance,
            entry.source_record_id,
            entry.transaction_datetime.isoformat(),
            str(entry.transaction_type),
            str(entry.ledger_origin),
            str(entry.source_leave_type) if entry.source_leave_type else None,
            str(entry.target_leave_type) if entry.target_leave_type else None,
            entry.source_minutes,
            entry.target_minutes,
            entry.note,
            entry.created_at.isoformat(),
            entry.reversal_of_id,
        )
        cur = con.execute(
            "INSERT INTO balance_ledger(entry_date,entry_type,reason,comp_change,annual_change,comp_balance,annual_balance,source_record_id,transaction_datetime,transaction_type,ledger_origin,source_leave_type,target_leave_type,source_minutes,target_minutes,note,created_at,reversal_of_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            values,
        )
        entry.id = cur.lastrowid
        if connection is None:
            con.commit()
        return entry.id

    def all(self, origin: LedgerOrigin | None = None) -> list[LedgerEntry]:
        sql = "SELECT * FROM balance_ledger"
        args = ()
        if origin:
            sql += " WHERE ledger_origin=?"
            args = (str(origin),)
        sql += " ORDER BY transaction_datetime,id"
        return [self._map(x) for x in self.db.connection.execute(sql, args)]

    def current_balances(self) -> tuple[int, int]:
        row = self.db.connection.execute(
            "SELECT comp_balance,annual_balance FROM balance_ledger ORDER BY transaction_datetime DESC,id DESC LIMIT 1"
        ).fetchone()
        return (row[0], row[1]) if row else (0, 0)

    def save_conversion(
        self, service, source_type, target_type, minutes, note="", when=None
    ):
        """Validate and insert both sides of a conversion in one SQLite transaction."""
        with self.db.transaction() as con:
            comp, annual = self.current_balances()
            entry = service.convert_leave(
                source_type, target_type, minutes, comp, annual, note, when
            )
            self.add(entry, con)
        return entry

    def save_reversal(self, service, original, note="", when=None):
        with self.db.transaction() as con:
            if con.execute(
                "SELECT 1 FROM balance_ledger WHERE reversal_of_id=?", (original.id,)
            ).fetchone():
                raise ValueError("此筆轉換已撤銷。")
            comp, annual = self.current_balances()
            entry = service.reverse_conversion(original, comp, annual, note, when)
            self.add(entry, con)
        return entry

    def rebuild_for_records(
        self,
        service,
        records,
        annual_opening=0,
        priority=DeductionPriority.COMP_TIME_FIRST,
        calendar=None,
        tracking_start_date=None,
        today=None,
    ):
        """Atomically replace derived events while preserving manual audit events."""
        manual = self.all(LedgerOrigin.MANUAL)
        rebuilt = service.recalculate_balances(
            records,
            annual_opening=annual_opening,
            priority=priority,
            manual_transactions=manual,
            calendar=calendar,
            tracking_start_date=tracking_start_date,
            today=today,
        )
        with self.db.transaction() as con:
            con.execute(
                "DELETE FROM balance_ledger WHERE ledger_origin=?",
                (str(LedgerOrigin.SYSTEM),),
            )
            for entry in rebuilt:
                if entry.ledger_origin == LedgerOrigin.MANUAL and entry.id:
                    con.execute(
                        "UPDATE balance_ledger SET comp_balance=?,annual_balance=? WHERE id=?",
                        (entry.comp_balance, entry.annual_balance, entry.id),
                    )
                elif entry.ledger_origin == LedgerOrigin.SYSTEM:
                    self.add(entry, con)
        return rebuilt

    @staticmethod
    def _map(x):
        return LedgerEntry(
            date.fromisoformat(x["entry_date"]),
            x["entry_type"],
            x["reason"],
            x["comp_change"],
            x["annual_change"],
            x["comp_balance"],
            x["annual_balance"],
            x["source_record_id"],
            x["id"],
            datetime.fromisoformat(x["transaction_datetime"]),
            TransactionType(x["transaction_type"]),
            LedgerOrigin(x["ledger_origin"]),
            LeaveType(x["source_leave_type"]) if x["source_leave_type"] else None,
            LeaveType(x["target_leave_type"]) if x["target_leave_type"] else None,
            x["source_minutes"],
            x["target_minutes"],
            x["note"],
            datetime.fromisoformat(x["created_at"]),
            x["reversal_of_id"],
        )
