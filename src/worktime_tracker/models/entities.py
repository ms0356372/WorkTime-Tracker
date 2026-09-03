"""Domain models. Durations and balances are always integer minutes."""
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from enum import StrEnum

class WorkdayType(StrEnum):
    NORMAL = "正常工作日"
    REST = "休息日"
    HOLIDAY = "假日"
    COMP_LEAVE = "補休"
    ANNUAL_LEAVE = "特休"
    OTHER = "其他"

class LeaveType(StrEnum):
    COMP_TIME = "COMP_TIME"
    ANNUAL_LEAVE = "ANNUAL_LEAVE"

class DeductionPriority(StrEnum):
    COMP_TIME_FIRST = "COMP_TIME_FIRST"
    ANNUAL_LEAVE_FIRST = "ANNUAL_LEAVE_FIRST"

class TransactionType(StrEnum):
    WORKTIME_EARN = "WORKTIME_EARN"
    WORKTIME_DEDUCTION = "WORKTIME_DEDUCTION"
    MONTHLY_SETTLEMENT = "MONTHLY_SETTLEMENT"
    LEAVE_CONVERSION = "LEAVE_CONVERSION"
    REVERSAL = "REVERSAL"
    ADJUSTMENT = "ADJUSTMENT"
    MISSING_WORKDAY_DEDUCTION = "MISSING_WORKDAY_DEDUCTION"

class LedgerOrigin(StrEnum):
    SYSTEM = "SYSTEM"
    MANUAL = "MANUAL"

@dataclass(slots=True)
class WorkRecord:
    work_date: date
    clock_in: str | None = None
    clock_out: str | None = None
    break_start: str | None = "12:00"
    break_end: str | None = "13:00"
    deduct_break: bool = True
    standard_minutes: int = 480
    note: str = ""
    workday_type: WorkdayType = WorkdayType.NORMAL
    overnight: bool = False
    id: int | None = None

@dataclass(slots=True)
class LedgerEntry:
    """An immutable audit event; balances are derived snapshots after the event."""
    entry_date: date
    entry_type: str
    reason: str
    comp_change: int = 0
    annual_change: int = 0
    comp_balance: int = 0
    annual_balance: int = 0
    source_record_id: int | None = None
    id: int | None = None
    transaction_datetime: datetime | None = None
    transaction_type: TransactionType = TransactionType.WORKTIME_EARN
    ledger_origin: LedgerOrigin = LedgerOrigin.SYSTEM
    source_leave_type: LeaveType | None = None
    target_leave_type: LeaveType | None = None
    source_minutes: int | None = None
    target_minutes: int | None = None
    note: str = ""
    created_at: datetime | None = None
    reversal_of_id: int | None = None

    def __post_init__(self) -> None:
        if self.transaction_datetime is None:
            self.transaction_datetime = datetime.combine(self.entry_date, time.min)
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

    @property
    def comp_time_change(self) -> int: return self.comp_change
    @property
    def annual_leave_change(self) -> int: return self.annual_change
    @property
    def comp_time_balance_after(self) -> int: return self.comp_balance
    @property
    def annual_leave_balance_after(self) -> int: return self.annual_balance

@dataclass(slots=True)
class LeaveCycle:
    start_date: date
    end_date: date
    total_minutes: int
    id: int | None = None
