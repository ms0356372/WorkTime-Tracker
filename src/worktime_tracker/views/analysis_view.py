"""Selectable-month lightweight work and leave analysis dashboard."""

from datetime import date
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
from worktime_tracker.services.analytics_service import (
    calculate_month_summary,
    calculate_year_summary,
)
from worktime_tracker.utils.formatting import format_minutes
from worktime_tracker.utils.months import next_month, previous_month


class AnalysisView:
    def __init__(self, records, ledger):
        self.records = records
        self.ledger = ledger
        today = date.today()
        self.selected_year = today.year
        self.selected_month = today.month

    def build(self):
        self.heading = toga.Label("")
        self.summary = toga.Label("")
        navigation = toga.Box(
            children=[
                toga.Button("<", on_press=self.show_previous_month),
                self.heading,
                toga.Button(">", on_press=self.show_next_month),
            ],
            style=Pack(direction=ROW, gap=8),
        )
        content = toga.Box(
            children=[navigation, self.summary],
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
        if not hasattr(self, "summary"):
            return
        rows = self.records.all()
        month = calculate_month_summary(rows, self.selected_year, self.selected_month)
        year = calculate_year_summary(rows, self.selected_year)
        comp, annual = self.ledger.current_balances()
        self.heading.text = f"{self.selected_year} 年 {self.selected_month} 月"
        self.summary.text = f"【{self.selected_year} 年 {self.selected_month} 月】\n總工時\n{format_minutes(month.work_minutes)}\n\n出勤天數\n{month.workdays} 天\n\n平均每日工時\n{format_minutes(month.average_minutes)}\n\n超時\n{format_minutes(month.overtime_minutes)}\n\n不足\n{format_minutes(month.shortfall_minutes)}\n\n【{self.selected_year} 年度】\n年度總工時\n{format_minutes(year.work_minutes)}\n\n年度出勤天數\n{year.workdays} 天\n\n【假別】\n補休餘額\n{format_minutes(comp)}\n\n特休餘額\n{format_minutes(annual)}"
