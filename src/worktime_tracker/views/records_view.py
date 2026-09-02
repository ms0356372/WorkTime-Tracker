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
    def __init__(self, records, ledger, settings, on_change=None):
        self.records = records
        self.service = WorkRecordService(records, ledger, settings)
        self.on_change = on_change

    def build(self):
        self.app = toga.App.app
        self.editing_id = None
        self.date = toga.DateInput(value=date.today())
        self.start = toga.TimeInput()
        self.end = toga.TimeInput()
        self.note = toga.TextInput(placeholder="備註")
        self.result = toga.Label("")
        self.recent_box = toga.Box(style=Pack(direction=COLUMN, gap=6))
        self.recent_records_host = toga.Box(
            children=[self.recent_box], style=Pack(direction=COLUMN)
        )
        form = toga.Box(
            children=[
                toga.Label("新增每日紀錄"),
                toga.Label("日期"),
                self.date,
                toga.Label("上班時間"),
                self.start,
                toga.Label("下班時間"),
                self.end,
                toga.Label("備註"),
                self.note,
                toga.Button("儲存紀錄", on_press=self.save),
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
            record = WorkRecord(
                self.date.value,
                self.start.value.strftime("%H:%M"),
                self.end.value.strftime("%H:%M"),
                note=self.note.value,
                id=self.editing_id,
            )
            self.service.save(record)
            self.editing_id = record.id
            self.refresh()
            if self.on_change:
                self.on_change()
            await self.app.main_window.dialog(
                toga.InfoDialog("紀錄已儲存", "工時與假別餘額已重新計算。")
            )
        except Exception as exc:
            await self.app.main_window.dialog(toga.ErrorDialog("無法儲存", str(exc)))

    def load(self, record):
        self.editing_id = record.id
        self.date.value = record.work_date
        self.start.value = datetime.strptime(record.clock_in, "%H:%M").time()
        self.end.value = datetime.strptime(record.clock_out, "%H:%M").time()
        self.note.value = record.note

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
