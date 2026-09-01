"""Validated, integer-only leave conversion and reversal operations."""
from datetime import datetime
from fractions import Fraction
from worktime_tracker.models import (LedgerEntry, LedgerOrigin, LeaveType,
                                     TransactionType)
from .worktime_calculator import ValidationError

class LeaveConversionService:
    """Convert leave using an extensible rational ratio (default 1:1)."""
    def __init__(self, conversion_ratio: Fraction = Fraction(1, 1)) -> None:
        if conversion_ratio <= 0:
            raise ValueError("轉換比例必須大於 0。")
        self.conversion_ratio = conversion_ratio

    def convert_leave(self, source_type: LeaveType, target_type: LeaveType, minutes: int,
                      comp_balance: int, annual_balance: int, note: str = "",
                      transaction_datetime: datetime | None = None) -> LedgerEntry:
        if source_type == target_type:
            raise ValidationError("來源假別與目的假別不可相同。")
        if minutes <= 0:
            raise ValidationError("請輸入大於 0 的轉換時數。")
        source_balance = comp_balance if source_type == LeaveType.COMP_TIME else annual_balance
        if minutes > source_balance:
            label = "補休" if source_type == LeaveType.COMP_TIME else "特休"
            raise ValidationError(f"{label}餘額不足，目前可轉換時數為 {self._format(source_balance)}。")
        converted = minutes * self.conversion_ratio.numerator
        denominator = self.conversion_ratio.denominator
        if converted % denominator:
            raise ValidationError("轉換比例無法產生完整分鐘，請調整轉換時數。")
        target_minutes = converted // denominator
        comp_change = -minutes if source_type == LeaveType.COMP_TIME else target_minutes
        annual_change = -minutes if source_type == LeaveType.ANNUAL_LEAVE else target_minutes
        when = transaction_datetime or datetime.now().astimezone()
        source_label = "補休" if source_type == LeaveType.COMP_TIME else "特休"
        target_label = "補休" if target_type == LeaveType.COMP_TIME else "特休"
        reason = note.strip() or f"{source_label}轉{target_label} {self._format(minutes)}"
        return LedgerEntry(when.date(), "假別轉換", reason, comp_change, annual_change,
                           comp_balance + comp_change, annual_balance + annual_change,
                           transaction_datetime=when, transaction_type=TransactionType.LEAVE_CONVERSION,
                           ledger_origin=LedgerOrigin.MANUAL, source_leave_type=source_type,
                           target_leave_type=target_type, source_minutes=minutes,
                           target_minutes=target_minutes, note=reason)

    def reverse_conversion(self, original: LedgerEntry, comp_balance: int,
                           annual_balance: int, note: str = "",
                           transaction_datetime: datetime | None = None) -> LedgerEntry:
        if original.transaction_type != TransactionType.LEAVE_CONVERSION:
            raise ValidationError("只有假別轉換紀錄可以撤銷。")
        if original.id is None:
            raise ValidationError("原始轉換尚未儲存，無法撤銷。")
        needed_comp = max(original.comp_change, 0)
        needed_annual = max(original.annual_change, 0)
        if comp_balance < needed_comp:
            raise ValidationError("目前補休餘額不足，無法完整撤銷此筆轉換。")
        if annual_balance < needed_annual:
            raise ValidationError("目前特休餘額不足，無法完整撤銷此筆轉換。")
        when = transaction_datetime or datetime.now().astimezone()
        reason = note.strip() or f"撤銷轉換 #{original.id}"
        return LedgerEntry(when.date(), "撤銷轉換", reason, -original.comp_change,
                           -original.annual_change, comp_balance-original.comp_change,
                           annual_balance-original.annual_change,
                           transaction_datetime=when, transaction_type=TransactionType.REVERSAL,
                           ledger_origin=LedgerOrigin.MANUAL,
                           source_leave_type=original.target_leave_type,
                           target_leave_type=original.source_leave_type,
                           source_minutes=original.target_minutes,
                           target_minutes=original.source_minutes, note=reason,
                           reversal_of_id=original.id)

    @staticmethod
    def _format(minutes: int) -> str:
        hours, remainder = divmod(minutes, 60)
        return f"{hours} 小時" + (f" {remainder} 分" if remainder else "")
