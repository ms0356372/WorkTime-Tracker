"""Lightweight monthly, yearly, and leave analysis dashboard."""

from datetime import date
import toga
from toga.style import Pack
from toga.style.pack import COLUMN
from worktime_tracker.services.analytics_service import (
    calculate_month_summary,
    calculate_year_summary,
)
from worktime_tracker.utils.formatting import format_minutes


class AnalysisView:
    def __init__(self, records, ledger):
        self.records = records
        self.ledger = ledger

    def build(self):
        self.summary = toga.Label("")
        content = toga.Box(
            children=[self.summary], style=Pack(direction=COLUMN, margin=16)
        )
        self.container = toga.ScrollContainer(content=content, style=Pack(flex=1))
        self.refresh()
        return self.container

    def refresh(self):
        if not hasattr(self, "summary"):
            return
        today = date.today()
        rows = self.records.all()
        month = calculate_month_summary(rows, today.year, today.month)
        year = calculate_year_summary(rows, today.year)
        comp, annual = self.ledger.current_balances()
        self.summary.text = f"【本月】\n本月總工時\n{format_minutes(month.work_minutes)}\n\n本月出勤天數\n{month.workdays} 天\n\n平均每日工時\n{format_minutes(month.average_minutes)}\n\n本月超時\n{format_minutes(month.overtime_minutes)}\n\n本月不足\n{format_minutes(month.shortfall_minutes)}\n\n【年度】\n年度總工時\n{format_minutes(year.work_minutes)}\n\n年度出勤天數\n{year.workdays} 天\n\n【假別】\n補休餘額\n{format_minutes(comp)}\n\n特休餘額\n{format_minutes(annual)}"
