"""Responsive settings, annual leave, and conversion controls."""

from datetime import date
import toga
from toga.style import Pack
from toga.style.pack import COLUMN
from worktime_tracker.models import DeductionPriority, LeaveType
from worktime_tracker.services.leave_conversion_service import LeaveConversionService
from worktime_tracker.services.record_service import WorkRecordService
from worktime_tracker.utils.formatting import format_minutes


class SettingsView:
    def __init__(
        self,
        settings_repository,
        ledger_repository,
        records_repository=None,
        on_change=None,
    ):
        self.settings = settings_repository
        self.ledger = ledger_repository
        self.records = records_repository
        self.on_change = on_change
        self.conversions = LeaveConversionService()

    def build(self):
        self.app = toga.App.app
        current = self.settings.deduction_priority()
        total = int(self.settings.get("annual_leave_total_minutes", "0") or 0)
        settlement = self.settings.get(
            "annual_leave_settlement_date", f"{date.today().year}-12-31"
        )
        self.priority = toga.Selection(
            items=["補休優先", "特休優先"],
            value="補休優先"
            if current == DeductionPriority.COMP_TIME_FIRST
            else "特休優先",
            on_change=self.change_priority,
        )
        self.annual_hours = toga.NumberInput(min=0, step=1, value=total // 60)
        self.settlement = toga.DateInput(value=date.fromisoformat(settlement))
        self.annual_summary = toga.Label("")
        self.source = toga.Selection(
            items=["補休", "特休"], value="補休", on_change=self.change_source
        )
        self.target = toga.Label("特休")
        self.hours = toga.NumberInput(min=0, step=1, value=0)
        self.minutes = toga.NumberInput(min=0, max=59, step=1, value=0)
        self.note = toga.TextInput(placeholder="備註（選填）")
        self.balances = toga.Label("")
        self.history = toga.Selection(items=self._history_items())
        children = [
            toga.Label("工時不足扣除順序"),
            self.priority,
            toga.Label("年度特休"),
            toga.Label("今年特休總時數（小時）"),
            self.annual_hours,
            toga.Label("特休結算日"),
            self.settlement,
            toga.Button("儲存年度特休設定", on_press=self.save_annual_leave),
            self.annual_summary,
            self.balances,
            toga.Label("補休 / 特休轉換"),
            toga.Label("轉換來源"),
            self.source,
            toga.Label("轉換至"),
            self.target,
            toga.Label("時數"),
            self.hours,
            toga.Label("小時"),
            self.minutes,
            toga.Label("分"),
            toga.Label("備註"),
            self.note,
            toga.Button("確認轉換", on_press=self.confirm_conversion),
            toga.Label("轉換紀錄"),
            self.history,
            toga.Button("撤銷選取的轉換", on_press=self.reverse_selected),
        ]
        content = toga.Box(
            children=children, style=Pack(direction=COLUMN, margin=16, gap=8)
        )
        self.container = toga.ScrollContainer(content=content, style=Pack(flex=1))
        self.refresh()
        return self.container

    async def change_priority(self, widget):
        value = (
            DeductionPriority.COMP_TIME_FIRST
            if widget.value == "補休優先"
            else DeductionPriority.ANNUAL_LEAVE_FIRST
        )
        self.settings.set("leave_deduction_priority", str(value))
        if self.records:
            WorkRecordService(self.records, self.ledger, self.settings).rebuild_ledger()
        self._notify()

    async def change_source(self, widget):
        self.target.text = "特休" if widget.value == "補休" else "補休"

    async def save_annual_leave(self, widget):
        total = int(self.annual_hours.value or 0) * 60
        self.settings.set("annual_leave_total_minutes", str(total))
        self.settings.set(
            "annual_leave_settlement_date", self.settlement.value.isoformat()
        )
        if self.records:
            WorkRecordService(self.records, self.ledger, self.settings).rebuild_ledger()
        self.refresh()
        self._notify()
        await self.app.main_window.dialog(
            toga.InfoDialog("設定已儲存", "年度特休與結算日已更新。")
        )

    async def confirm_conversion(self, widget):
        source = (
            LeaveType.COMP_TIME
            if self.source.value == "補休"
            else LeaveType.ANNUAL_LEAVE
        )
        target = (
            LeaveType.ANNUAL_LEAVE
            if source == LeaveType.COMP_TIME
            else LeaveType.COMP_TIME
        )
        minutes = int(self.hours.value or 0) * 60 + int(self.minutes.value or 0)
        comp, annual = self.ledger.current_balances()
        try:
            preview = self.conversions.convert_leave(
                source, target, minutes, comp, annual, self.note.value
            )
            message = f"此次將{self.source.value} {format_minutes(minutes)}轉換成{self.target.text}。\n轉換後補休：{format_minutes(preview.comp_balance)}\n轉換後特休：{format_minutes(preview.annual_balance)}\n確定要執行嗎？"
            if await self.app.main_window.dialog(
                toga.ConfirmDialog("確認轉換", message)
            ):
                self.ledger.save_conversion(
                    self.conversions, source, target, minutes, self.note.value
                )
                self.refresh()
                self._notify()
                await self.app.main_window.dialog(
                    toga.InfoDialog("完成", "假別時數已轉換並寫入流水帳。")
                )
        except Exception as exc:
            await self.app.main_window.dialog(toga.ErrorDialog("無法轉換", str(exc)))

    def _history_items(self):
        return [
            f"#{e.id}｜{e.entry_date.isoformat()}｜{e.entry_type}｜{e.source_minutes or 0} 分"
            for e in self.ledger.all()
            if str(e.transaction_type) in {"LEAVE_CONVERSION", "REVERSAL"}
        ]

    def refresh(self):
        if not hasattr(self, "balances"):
            return
        comp, annual = self.ledger.current_balances()
        total = int(self.settings.get("annual_leave_total_minutes", "0") or 0)
        used = max(total - annual, 0)
        self.balances.text = (
            f"目前補休\n{format_minutes(comp)}\n\n目前特休\n{format_minutes(annual)}"
        )
        self.annual_summary.text = f"年度特休：{format_minutes(total)}\n已使用：{format_minutes(used)}\n剩餘：{format_minutes(annual)}"
        self.history.items = self._history_items()

    def _notify(self):
        if self.on_change:
            self.on_change()

    def _notify(self):
        if self.on_change:
            self.on_change()

    async def reverse_selected(self, widget):
        if not self.history.value or not self.history.value.startswith("#"):
            await self.app.main_window.dialog(
                toga.ErrorDialog("無法撤銷", "請先選擇一筆轉換紀錄。")
            )
            return
        entry_id = int(self.history.value.split("｜", 1)[0][1:])
        original = next((e for e in self.ledger.all() if e.id == entry_id), None)
        if original is None or str(original.transaction_type) != "LEAVE_CONVERSION":
            await self.app.main_window.dialog(
                toga.ErrorDialog("無法撤銷", "只能撤銷原始假別轉換。")
            )
            return
        if not await self.app.main_window.dialog(
            toga.ConfirmDialog("撤銷轉換", f"確定要建立 #{entry_id} 的反向流水紀錄嗎？")
        ):
            return
        try:
            self.ledger.save_reversal(self.conversions, original)
            self.refresh()
            self._notify()
            await self.app.main_window.dialog(
                toga.InfoDialog("完成", "已建立反向 Ledger。")
            )
        except Exception as exc:
            await self.app.main_window.dialog(toga.ErrorDialog("無法撤銷", str(exc)))
