"""Responsive four-metric home dashboard."""

from datetime import date
import toga
from toga.style import Pack
from toga.style.pack import COLUMN
from worktime_tracker.services.analytics_service import calculate_month_summary
from worktime_tracker.services.worktime_calculator import calculate_work_minutes
from worktime_tracker.utils.formatting import format_minutes


class DashboardView:
    def __init__(self, repository, ledger_repository):
        self.repository = repository
        self.ledger = ledger_repository

    def build(self):
        self.labels = {
            name: toga.Label("", style=Pack(margin_bottom=14))
            for name in ("today", "month", "comp", "annual")
        }
        content = toga.Box(
            children=list(self.labels.values()), style=Pack(direction=COLUMN, margin=16)
        )
        self.container = toga.ScrollContainer(content=content, style=Pack(flex=1))
        self.refresh()
        return self.container

    def refresh(self):
        today = date.today()
        records = self.repository.all()
        today_record = next((r for r in records if r.work_date == today), None)
        month = calculate_month_summary(records, today.year, today.month)
        comp, annual = self.ledger.current_balances()
        self.labels[
            "today"
        ].text = f"今天工時\n{format_minutes(calculate_work_minutes(today_record) if today_record else 0)}"
        self.labels["month"].text = f"本月工時\n{format_minutes(month.work_minutes)}"
        self.labels["comp"].text = f"目前補休\n{format_minutes(comp)}"
        self.labels["annual"].text = f"剩餘特休\n{format_minutes(annual)}"
