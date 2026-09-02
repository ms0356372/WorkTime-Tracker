"""Current-month work record list."""

from datetime import date
import toga
from toga.style import Pack
from toga.style.pack import COLUMN
from worktime_tracker.services.worktime_calculator import (
    calculate_daily_difference,
    calculate_work_minutes,
)
from worktime_tracker.utils.formatting import format_minutes


class MonthlyRecordsView:
    def __init__(self, repository, on_edit):
        self.repository = repository
        self.on_edit = on_edit

    def build(self):
        self.heading = toga.Label("")
        self.list = toga.Box(style=Pack(direction=COLUMN, gap=8))
        content = toga.Box(
            children=[self.heading, toga.Label("本月紀錄"), self.list],
            style=Pack(direction=COLUMN, margin=16, gap=10),
        )
        self.container = toga.ScrollContainer(content=content, style=Pack(flex=1))
        self.refresh()
        return self.container

    def refresh(self):
        if not hasattr(self, "list"):
            return
        today = date.today()
        self.heading.text = f"{today.year} 年 {today.month} 月"
        self.list.children.clear()
        records = self.repository.for_month(today.year, today.month)
        if not records:
            self.list.add(
                toga.Label("目前尚無本月工時紀錄\n可至「紀錄」新增每日工時。")
            )
            return
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
                        f"日期：{selected.work_date.isoformat()}\n"
                        f"上班：{selected.clock_in}\n下班：{selected.clock_out}\n"
                        f"午休：{selected.break_start} - {selected.break_end}\n"
                        f"實際工作：{format_minutes(work)}\n"
                        f"每日基準：{format_minutes(selected.standard_minutes)}\n"
                        f"{delta}\n備註：{selected.note or '無'}\n\n"
                        "已載入至「紀錄」頁，可切換頁籤修改或刪除。",
                    )
                )

            self.list.add(
                toga.Button(
                    f"{record.work_date:%m/%d}\n{record.clock_in} - {record.clock_out}\n工作：{format_minutes(actual)}\n{change}",
                    on_press=show_detail,
                )
            )
