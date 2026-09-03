"""Responsive settings, annual leave, and conversion controls."""

from datetime import date, datetime
from pathlib import Path
import traceback
import toga
from toga.style import Pack
from toga.style.pack import COLUMN
from worktime_tracker.models import DeductionPriority, LeaveType
from worktime_tracker.services.leave_conversion_service import LeaveConversionService
from worktime_tracker.services.record_service import WorkRecordService
from worktime_tracker.services.worktime_calculator import validate_lunch_break
from worktime_tracker.services.backup_service import (
    backup_filename,
    create_backup,
    inspect_backup,
    restore_backup,
)
from worktime_tracker.services.android_file_service import BACKUP_MIME, file_service_for
from worktime_tracker.utils.formatting import format_minutes
from worktime_tracker.utils.leave_year import get_current_leave_year_range


class SettingsView:
    def __init__(
        self,
        settings_repository,
        ledger_repository,
        records_repository=None,
        on_change=None,
        data_directory=None,
        calendar=None,
    ):
        self.settings = settings_repository
        self.ledger = ledger_repository
        self.records = records_repository
        self.on_change = on_change
        self.conversions = LeaveConversionService()
        self.data_directory = Path(data_directory) if data_directory else None
        self.calendar = calendar

    def build(self):
        self.app = toga.App.app
        current = self.settings.deduction_priority()
        total = int(self.settings.get("annual_leave_total_minutes", "0") or 0)
        daily_standard = int(self.settings.get("daily_standard_minutes", "480") or 480)
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
        self.daily_hours = toga.NumberInput(min=1, step=1, value=daily_standard // 60)
        self.settlement = toga.DateInput(value=date.fromisoformat(settlement))
        self.leave_year_summary = toga.Label("")
        self.annual_summary = toga.Label("")
        lunch_start, lunch_end = self.settings.lunch_break()
        self.lunch_start = toga.TimeInput(
            value=datetime.strptime(lunch_start, "%H:%M").time()
        )
        self.lunch_end = toga.TimeInput(
            value=datetime.strptime(lunch_end, "%H:%M").time()
        )
        self.source = toga.Selection(
            items=["補休", "特休"], value="補休", on_change=self.change_source
        )
        self.target = toga.Label("特休")
        self.hours = toga.NumberInput(min=0, step=1, value=0)
        self.minutes = toga.NumberInput(min=0, max=59, step=1, value=0)
        self.note = toga.TextInput(placeholder="備註（選填）")
        self.balances = toga.Label("")
        self.history = toga.Selection(items=self._history_items())
        tracking_start = (
            self.settings.tracking_start_date()
            if hasattr(self.settings, "tracking_start_date")
            else date.today()
        )
        self.tracking_start = toga.DateInput(value=tracking_start)
        self.calendar_status = toga.Label("")
        self.override_date = toga.DateInput(value=date.today())
        self.override_type = toga.Selection(items=["上班日", "非上班日"], value="非上班日")
        self.override_note = toga.TextInput(placeholder="公司補班／公司休假")
        self.override_history = toga.Selection(items=[])
        children = [
            toga.Label("每日標準工時（小時）"),
            self.daily_hours,
            toga.Button("儲存每日標準工時", on_press=self.save_daily_standard),
            toga.Label("工時不足扣除順序"),
            self.priority,
            toga.Label("年度特休"),
            toga.Label("今年特休總時數（小時）"),
            self.annual_hours,
            toga.Label("特休結算日"),
            self.settlement,
            toga.Label("年度計算期間為：特休結算日隔天至下一年度結算日當天。"),
            toga.Label("若結算日為 6/30，則 2026/7/1～2027/6/30 為同一年度。"),
            self.leave_year_summary,
            toga.Button("儲存年度特休設定", on_press=self.save_annual_leave),
            self.annual_summary,
            self.balances,
            toga.Label("午休設定"),
            toga.Label("午休開始時間"),
            self.lunch_start,
            toga.Label("午休結束時間"),
            self.lunch_end,
            toga.Button("儲存午休設定", on_press=self.save_lunch_break),
            toga.Label("工作日曆"),
            toga.Label("基本工作日：星期一～星期五"),
            toga.Label("國定假日：使用台灣政府官方行事曆"),
            self.calendar_status,
            toga.Button("更新國定假日", on_press=self.sync_holidays),
            toga.Label("工時計算起始日"),
            self.tracking_start,
            toga.Label("起始日之後的正常上班日，若整天沒有工時紀錄，將視為不足每日標準工時。"),
            toga.Button("儲存工時計算起始日", on_press=self.save_tracking_start),
            toga.Label("特殊日期"),
            self.override_date,
            self.override_type,
            self.override_note,
            toga.Button("新增特殊日期", on_press=self.save_override),
            self.override_history,
            toga.Button("刪除選取的特殊日期", on_press=self.delete_override),
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
            toga.Label("資料管理"),
            toga.Button("完整備份", on_press=self.create_full_backup),
            toga.Button("還原備份", on_press=self.restore_full_backup),
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

    async def save_daily_standard(self, widget):
        minutes = int(self.daily_hours.value or 0) * 60
        if minutes <= 0:
            await self.app.main_window.dialog(
                toga.ErrorDialog("無法儲存", "每日標準工時必須大於 0。")
            )
            return
        self.settings.set("daily_standard_minutes", str(minutes))
        if self.records:
            WorkRecordService(
                self.records, self.ledger, self.settings, self.calendar
            ).rebuild_ledger()
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

    async def save_lunch_break(self, widget):
        start = self.lunch_start.value.strftime("%H:%M")
        end = self.lunch_end.value.strftime("%H:%M")
        try:
            validate_lunch_break(start, end)
        except ValueError as exc:
            await self.app.main_window.dialog(toga.ErrorDialog("無法儲存", str(exc)))
            return
        self.settings.set_lunch_break(start, end)
        if self.records:
            WorkRecordService(
                self.records, self.ledger, self.settings
            ).apply_global_lunch_break()
        self.refresh()
        self._notify()
        await self.app.main_window.dialog(
            toga.InfoDialog("午休設定已儲存", "歷史工時與假別餘額已重新計算。")
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

    async def save_tracking_start(self, widget):
        if self.tracking_start.value > date.today():
            await self.app.main_window.dialog(toga.ErrorDialog("無法儲存", "工時計算起始日不能晚於今天。"))
            return
        self.settings.set("work_tracking_start_date", self.tracking_start.value.isoformat())
        if self.records:
            WorkRecordService(self.records, self.ledger, self.settings, self.calendar).rebuild_ledger()
        self._notify()

    async def sync_holidays(self, widget):
        if not self.calendar:
            return
        years = (date.today().year, date.today().year + 1)
        succeeded = [self.calendar.sync_year(year) for year in years]
        self.refresh()
        title = "國定假日已更新" if any(succeeded) else "國定假日資料更新失敗"
        message = "已使用最新官方資料。" if any(succeeded) else "目前使用本機已儲存資料。"
        await self.app.main_window.dialog(toga.InfoDialog(title, message))
        if any(succeeded) and self.records:
            WorkRecordService(self.records, self.ledger, self.settings, self.calendar).rebuild_ledger()
            self._notify()

    async def save_override(self, widget):
        if not self.calendar:
            return
        kind = "WORKDAY" if self.override_type.value == "上班日" else "NON_WORKDAY"
        self.calendar.overrides.save(self.override_date.value, kind, self.override_note.value)
        if self.records:
            WorkRecordService(self.records, self.ledger, self.settings, self.calendar).rebuild_ledger()
        self.refresh()
        self._notify()

    async def delete_override(self, widget):
        if not self.calendar or not self.override_history.value:
            return
        selected = date.fromisoformat(self.override_history.value.split("｜", 1)[0])
        self.calendar.overrides.delete(selected)
        if self.records:
            WorkRecordService(self.records, self.ledger, self.settings, self.calendar).rebuild_ledger()
        self.refresh()
        self._notify()

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
        configured = self.settings.get("annual_leave_settlement_date")
        if configured:
            settlement = date.fromisoformat(configured)
            self.settlement.value = settlement
            start, end = get_current_leave_year_range(
                date.today(), settlement.month, settlement.day
            )
            self.leave_year_summary.text = (
                f"目前年度：{start:%Y/%m/%d} ～ {end:%Y/%m/%d}"
            )
        else:
            self.leave_year_summary.text = "目前年度：尚未設定特休結算日"
        if self.calendar:
            statuses = self.calendar.holidays.status()
            self.calendar_status.text = "\n".join(
                f"{row['year']}：已更新（{row['holiday_count']} 日）" for row in statuses
            ) or "尚無本機國定假日資料"
            self.override_history.items = [
                f"{row['work_date']}｜{'上班日' if row['day_type'] == 'WORKDAY' else '非上班日'}｜{row['note']}"
                for row in self.calendar.overrides.all()
            ]

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

    def _backup_directory(self):
        path = self.data_directory or Path(self.app.paths.data)
        path = path / "backups"
        path.mkdir(parents=True, exist_ok=True)
        return path

    async def create_full_backup(self, widget):
        try:
            filename = backup_filename()
            temporary = create_backup(
                self.records.db, self._backup_directory() / filename
            )
            saved = await file_service_for(self.app).save_bytes(
                temporary.read_bytes(), filename, BACKUP_MIME
            )
            if saved:
                await self.app.main_window.dialog(
                    toga.InfoDialog("完整備份完成", f"檔案：{filename}")
                )
        except Exception as exc:
            traceback.print_exc()
            await self.app.main_window.dialog(
                toga.ErrorDialog("無法建立完整備份", str(exc))
            )

    async def restore_full_backup(self, widget):
        try:
            payload = await file_service_for(self.app).open_bytes(BACKUP_MIME)
            if payload is None:
                return
            selected = self._backup_directory() / "selected.worktimebackup"
            selected.write_bytes(payload)
            manifest, _ = inspect_backup(selected)
            information = (
                f"備份日期：{manifest['created_at']}\nAPP 版本：{manifest['app_version']}\n"
                f"工時紀錄：{manifest['record_count']} 筆\n備份格式：v{manifest['backup_format_version']}"
            )
            if not await self.app.main_window.dialog(
                toga.ConfirmDialog("備份資訊", information)
            ):
                return
            warning = "還原備份將取代目前手機中的工時資料與設定。\n目前資料會先自動建立安全備份。\n\n是否繼續？"
            if not await self.app.main_window.dialog(
                toga.ConfirmDialog("確認還原備份", warning)
            ):
                return
            result = restore_backup(self.records.db, selected, self._backup_directory())
            self.refresh()
            self._notify()
            comp, annual = self.ledger.current_balances()
            await self.app.main_window.dialog(
                toga.InfoDialog(
                    "資料還原完成",
                    f"工時紀錄：{result['record_count']} 筆\n補休：{format_minutes(comp)}\n特休：{format_minutes(annual)}",
                )
            )
        except Exception as exc:
            traceback.print_exc()
            await self.app.main_window.dialog(
                toga.ErrorDialog("無法還原備份", str(exc))
            )
