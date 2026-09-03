"""Selectable-month work record cards with stable dynamic replacement."""

from datetime import date
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
from worktime_tracker.services.worktime_calculator import calculate_work_minutes
from worktime_tracker.services.record_service import WorkRecordService
from worktime_tracker.utils.formatting import format_minutes
from worktime_tracker.utils.months import next_month, previous_month

EDIT_BUTTON_COLOR = "#1976D2"
DELETE_BUTTON_COLOR = "#D32F2F"
ACTION_TEXT_COLOR = "#FFFFFF"
CARD_BACKGROUND_COLOR = "#F5F5F5"


class MonthlyRecordsView:
    def __init__(self, repository, on_edit, ledger=None, settings=None, on_change=None):
        self.repository = repository
        self.on_edit = on_edit
        self.record_service = (
            WorkRecordService(repository, ledger, settings)
            if ledger and settings
            else None
        )
        self.on_change = on_change
        today = date.today()
        self.selected_year = today.year
        self.selected_month = today.month

    def build(self):
        self.heading = toga.Label("")
        self.list = toga.Box(style=Pack(direction=COLUMN, gap=8))
        self.list_host = toga.Box(children=[self.list], style=Pack(direction=COLUMN))
        navigation = toga.Box(
            children=[
                toga.Button("<", on_press=self.show_previous_month),
                self.heading,
                toga.Button(">", on_press=self.show_next_month),
            ],
            style=Pack(direction=ROW, gap=8),
        )
        content = toga.Box(
            children=[navigation, toga.Label("月份紀錄"), self.list_host],
            style=Pack(direction=COLUMN, margin=16, gap=10),
        )
        self.container = toga.ScrollContainer(content=content, style=Pack(flex=1))
        self.refresh()
        return self.container

    def show_previous_month(self, widget=None):
        self.selected_year, self.selected_month = previous_month(
            self.selected_year, self.selected_month
        )
        self.refresh()

    def show_next_month(self, widget=None):
        self.selected_year, self.selected_month = next_month(
            self.selected_year, self.selected_month
        )
        self.refresh()

    @staticmethod
    def _edit_handler(record, on_edit):
        def edit_record(widget):
            on_edit(record)

        return edit_record

    def _delete_handler(self, record):
        async def delete_record(widget):
            await self.delete_record(record)

        return delete_record

    async def delete_record(self, record):
        """Confirm and delete exactly one record through the shared service."""
        if not self.record_service:
            return
        confirmed = await toga.App.app.main_window.dialog(
            toga.ConfirmDialog(
                "確認刪除紀錄",
                f"確定要刪除 {record.work_date.isoformat()} 的工時紀錄嗎？\n\n"
                "此操作會重新計算補休與特休餘額。",
            )
        )
        if not confirmed:
            return
        self.record_service.delete(record.id)
        self.refresh()
        if self.on_change:
            self.on_change()

    def _record_card(self, record):
        """Build one compact card using the central work-time calculator."""
        actual = calculate_work_minutes(record)
        information = toga.Box(
            children=[
                toga.Label(f"{record.work_date:%m/%d}"),
                toga.Label(f"工時 {format_minutes(actual)}"),
            ],
            style=Pack(direction=COLUMN, flex=1, gap=4),
        )
        actions = toga.Box(
            children=[
                toga.Button(
                    "修改",
                    on_press=self._edit_handler(record, self.on_edit),
                    style=Pack(
                        background_color=EDIT_BUTTON_COLOR,
                        color=ACTION_TEXT_COLOR,
                        width=64,
                    ),
                ),
                toga.Button(
                    "刪除",
                    on_press=self._delete_handler(record),
                    style=Pack(
                        background_color=DELETE_BUTTON_COLOR,
                        color=ACTION_TEXT_COLOR,
                        width=64,
                    ),
                ),
            ],
            style=Pack(direction=ROW, gap=4),
        )
        return toga.Box(
            children=[information, actions],
            style=Pack(
                direction=ROW,
                background_color=CARD_BACKGROUND_COLOR,
                margin_bottom=8,
                gap=8,
            ),
        )

    def refresh(self):
        if not hasattr(self, "list_host"):
            return
        self.heading.text = f"{self.selected_year} 年 {self.selected_month} 月"
        records = self.repository.records_for_month(
            self.selected_year, self.selected_month
        )
        children = []
        if not records:
            children.append(toga.Label("此月份尚無工時紀錄"))
        else:
            children.extend(self._record_card(record) for record in records)
        replacement = toga.Box(children=children, style=Pack(direction=COLUMN, gap=8))
        self.list_host.replace(self.list, replacement)
        self.list = replacement
