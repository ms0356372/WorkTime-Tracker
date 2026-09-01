"""Settings and leave-management controls."""
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
from worktime_tracker.models import DeductionPriority, LeaveType
from worktime_tracker.services.leave_conversion_service import LeaveConversionService

class SettingsView:
    def __init__(self, settings_repository, ledger_repository):
        self.settings = settings_repository
        self.ledger = ledger_repository
        self.conversions = LeaveConversionService()

    def build(self):
        self.app = toga.App.app
        current = self.settings.deduction_priority()
        self.priority = toga.Selection(items=["補休優先", "特休優先"], value="補休優先" if current == DeductionPriority.COMP_TIME_FIRST else "特休優先", on_change=self.change_priority)
        self.source = toga.Selection(items=["補休", "特休"], value="補休", on_change=self.change_source)
        self.target = toga.Label("特休")
        self.hours = toga.NumberInput(min=0, step=1, value=0)
        self.minutes = toga.NumberInput(min=0, max=59, step=1, value=0)
        self.note = toga.TextInput(placeholder="備註（選填）")
        comp, annual = self.ledger.current_balances()
        self.balances = toga.Label(f"目前補休：{comp//60} 小時 {comp%60} 分\n目前特休：{annual//60} 小時 {annual%60} 分")
        self.history = toga.Selection(items=self._history_items())
        return toga.Box(children=[toga.Label("工時不足扣除順序"),self.priority,self.balances,toga.Label("假別時數轉換"),toga.Box(children=[self.source,toga.Label("轉換至"),self.target],style=Pack(direction=ROW,gap=8)),toga.Box(children=[self.hours,toga.Label("小時"),self.minutes,toga.Label("分")],style=Pack(direction=ROW,gap=8)),self.note,toga.Button("確認轉換",on_press=self.confirm_conversion),toga.Label("轉換紀錄"),self.history,toga.Button("撤銷選取的轉換",on_press=self.reverse_selected)],style=Pack(direction=COLUMN,padding=16,gap=8))

    async def change_priority(self, widget):
        value = DeductionPriority.COMP_TIME_FIRST if widget.value == "補休優先" else DeductionPriority.ANNUAL_LEAVE_FIRST
        self.settings.set("leave_deduction_priority", str(value))

    async def change_source(self, widget): self.target.text = "特休" if widget.value == "補休" else "補休"

    async def confirm_conversion(self, widget):
        source = LeaveType.COMP_TIME if self.source.value == "補休" else LeaveType.ANNUAL_LEAVE
        target = LeaveType.ANNUAL_LEAVE if source == LeaveType.COMP_TIME else LeaveType.COMP_TIME
        minutes = int(self.hours.value or 0)*60 + int(self.minutes.value or 0)
        comp, annual = self.ledger.current_balances()
        try:
            preview = self.conversions.convert_leave(source,target,minutes,comp,annual,self.note.value)
            message=f"此次將{self.source.value} {minutes//60} 小時 {minutes%60} 分轉換成{self.target.text}。\n轉換後補休：{preview.comp_balance//60} 小時 {preview.comp_balance%60} 分\n轉換後特休：{preview.annual_balance//60} 小時 {preview.annual_balance%60} 分\n確定要執行嗎？"
            if await self.app.main_window.dialog(toga.ConfirmDialog("確認轉換",message)):
                self.ledger.save_conversion(self.conversions,source,target,minutes,self.note.value)
                self._refresh(); await self.app.main_window.dialog(toga.InfoDialog("完成","假別時數已轉換並寫入流水帳。"))
        except Exception as exc:
            message = str(exc) if exc.__class__.__name__ == "ValidationError" else "資料寫入失敗，請稍後再試。"
            await self.app.main_window.dialog(toga.ErrorDialog("無法轉換",message))

    def _history_items(self):
        return [f"#{e.id}｜{e.entry_date.isoformat()}｜{e.entry_type}｜{e.source_minutes or 0} 分" for e in self.ledger.all() if str(e.transaction_type) in {"LEAVE_CONVERSION","REVERSAL"}]

    def _refresh(self):
        comp, annual = self.ledger.current_balances()
        self.balances.text = f"目前補休：{comp//60} 小時 {comp%60} 分\n目前特休：{annual//60} 小時 {annual%60} 分"
        self.history.items.clear()
        self.history.items.extend(self._history_items())

    async def reverse_selected(self, widget):
        if not self.history.value or not self.history.value.startswith("#"):
            await self.app.main_window.dialog(toga.ErrorDialog("無法撤銷","請先選擇一筆轉換紀錄。")); return
        entry_id = int(self.history.value.split("｜",1)[0][1:])
        original = next((e for e in self.ledger.all() if e.id == entry_id), None)
        if original is None or str(original.transaction_type) != "LEAVE_CONVERSION":
            await self.app.main_window.dialog(toga.ErrorDialog("無法撤銷","只能撤銷原始假別轉換。")); return
        if not await self.app.main_window.dialog(toga.ConfirmDialog("撤銷轉換",f"確定要建立 #{entry_id} 的反向流水紀錄嗎？")): return
        try:
            self.ledger.save_reversal(self.conversions,original); self._refresh()
            await self.app.main_window.dialog(toga.InfoDialog("完成","已建立反向 Ledger，原始紀錄仍保留。"))
        except Exception as exc:
            message = str(exc) if exc.__class__.__name__ == "ValidationError" else "撤銷失敗，請確認此筆紀錄尚未撤銷。"
            await self.app.main_window.dialog(toga.ErrorDialog("無法撤銷",message))
