"""Daily record editor, result summary, and recent records."""

from datetime import date, datetime
import toga
from toga.style import Pack
from toga.style.pack import COLUMN
from worktime_tracker.models import WorkRecord
from worktime_tracker.services.record_service import WorkRecordService
from worktime_tracker.services.worktime_calculator import calculate_work_minutes
from worktime_tracker.utils.formatting import format_minutes


class RecordsView:
    def __init__(
        self, records, ledger, settings, on_change=None, on_edit_complete=None
    ):
        self.records = records
        self.service = WorkRecordService(records, ledger, settings)
        self.on_change = on_change
        self.on_edit_complete = on_edit_complete

    def build(self):
        self.app = toga.App.app
        self.editing_record_id = None
        self.editing_record_date = None
        self.heading = toga.Label("新增每日紀錄")
        self.date = toga.DateInput(value=date.today())
        self.start = toga.TimeInput()
        self.end = toga.TimeInput()
        self.note = toga.TextInput(placeholder="備註")
        self.save_button = toga.Button("儲存紀錄", on_press=self.save)
        self.cancel_button = toga.Button(
            "取消修改", on_press=self.cancel_edit, enabled=False
        )
        self.result = toga.Label("")
        self.recent_box = toga.Box(style=Pack(direction=COLUMN, gap=6))
        self.recent_records_host = toga.Box(
            children=[self.recent_box], style=Pack(direction=COLUMN)
        )
        form = toga.Box(
            children=[
                self.heading,
                toga.Label("日期"),
                self.date,
                toga.Label("上班時間"),
                self.start,
                toga.Label("下班時間"),
                self.end,
                toga.Label("備註"),
                self.note,
                self.save_button,
                self.cancel_button,
                self.result,
                toga.Label("最近紀錄"),
                self.recent_records_host,
            ],
            style=Pack(direction=COLUMN, margin=16, gap=8),
        )
        self.container = toga.ScrollContainer(content=form, style=Pack(flex=1))
        self.refresh()
        return self.container

    async def save(self, widget):
        try:
            editing = self.editing_record_id is not None
            record = WorkRecord(
                self.editing_record_date if editing else self.date.value,
                self.start.value.strftime("%H:%M"),
                self.end.value.strftime("%H:%M"),
                note=self.note.value,
                id=self.editing_record_id,
            )
            if editing:
                self.service.update(record)
            else:
                self.service.save(record)
            self.refresh()
            if self.on_change:
                self.on_change()
            await self.app.main_window.dialog(
                toga.InfoDialog(
                    "紀錄已更新" if editing else "紀錄已儲存",
                    "工時與假別餘額已重新計算。",
                )
            )
            if editing:
                self._reset_new_mode()
                if self.on_edit_complete:
                    self.on_edit_complete()
        except Exception as exc:
            await self.app.main_window.dialog(toga.ErrorDialog("無法儲存", str(exc)))

    def load(self, record):
        self.editing_record_id = record.id
        self.editing_record_date = record.work_date
        self.heading.text = f"編輯紀錄－{record.work_date:%Y/%m/%d}"
        self.save_button.text = "儲存修改"
        self.cancel_button.enabled = True
        self.date.enabled = False
        self.date.value = record.work_date
        self.start.value = datetime.strptime(record.clock_in, "%H:%M").time()
        self.end.value = datetime.strptime(record.clock_out, "%H:%M").time()
        self.note.value = record.note

    def cancel_edit(self, widget=None):
        """Leave edit mode without persisting any form values."""
        self._reset_new_mode()

    def _reset_new_mode(self):
        self.editing_record_id = None
        self.editing_record_date = None
        self.heading.text = "新增每日紀錄"
        self.save_button.text = "儲存紀錄"
        self.cancel_button.enabled = False
        self.date.enabled = True
        self.date.value = date.today()
        self.start.value = None
        self.end.value = None
        self.note.value = ""

    def refresh(self):
        if not hasattr(self, "recent_records_host"):
            return
        self.result.text = (
            f"本日工時\n{format_minutes(self.service.today_work_minutes())}"
        )
        self.refresh_recent_records()

    def refresh_recent_records(self):
        """Atomically replace only the dynamic list; never append to stale widgets."""
        records = self.records.recent(5)
        children = []
        if not records:
            children.append(toga.Label("目前尚無工時紀錄。"))
        for record in records:
            minutes = calculate_work_minutes(record)
            children.append(
                toga.Button(
                    f"{record.work_date:%m/%d}　{record.clock_in} - {record.clock_out}\n工時 {format_minutes(minutes)}",
                    on_press=lambda widget, r=record: self.load(r),
                )
            )
        replacement = toga.Box(children=children, style=Pack(direction=COLUMN, gap=6))
        self.recent_records_host.replace(self.recent_box, replacement)
        self.recent_box = replacement
