"""Selectable-month work record list with stable dynamic replacement."""

from datetime import date
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
from worktime_tracker.services.worktime_calculator import (
    calculate_daily_difference,
    calculate_work_minutes,
)
from worktime_tracker.utils.formatting import format_minutes
from worktime_tracker.utils.months import next_month, previous_month


class MonthlyRecordsView:
    def __init__(self, repository, on_edit):
        self.repository = repository
        self.on_edit = on_edit
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

    def refresh(self):
        if not hasattr(self, "list_host"):
            return
        self.heading.text = f"{self.selected_year} 年 {self.selected_month} 月"
        records = self.repository.records_for_month(
            self.selected_year, self.selected_month
        )
        children = []
        if not records:
            children.append(toga.Label("目前此月份沒有工時紀錄。"))
        for record in records:
            actual = calculate_work_minutes(record)
            diff = calculate_daily_difference(actual, record.standard_minutes)
            change = (
                f"補休：+{format_minutes(diff)}"
                if diff >= 0
                else f"不足：{format_minutes(-diff)}"
            )

            async def show_detail(widget, selected=record, work=actual, delta=change):
                self.on_edit(selected)
                await toga.App.app.main_window.dialog(
                    toga.InfoDialog(
                        "工時紀錄詳情",
                        f"日期：{selected.work_date.isoformat()}\n上班：{selected.clock_in}\n下班：{selected.clock_out}\n午休：{selected.break_start} - {selected.break_end}\n實際工作：{format_minutes(work)}\n每日基準：{format_minutes(selected.standard_minutes)}\n{delta}\n備註：{selected.note or '無'}\n\n已載入至「紀錄」頁，可切換頁籤修改或刪除。",
                    )
                )

            children.append(
                toga.Button(
                    f"{record.work_date:%m/%d}\n{record.clock_in} - {record.clock_out}\n工作：{format_minutes(actual)}\n{change}",
                    on_press=show_detail,
                )
            )
        replacement = toga.Box(children=children, style=Pack(direction=COLUMN, gap=8))
        self.list_host.replace(self.list, replacement)
        self.list = replacement
