"""BeeWare Toga mobile application composition root."""

from pathlib import Path

import toga
from toga.style import Pack
from worktime_tracker.config import APP_NAME
from worktime_tracker.database import (
    Database,
    LedgerRepository,
    SettingsRepository,
    WorkRecordRepository,
)
from worktime_tracker.views.analysis_view import AnalysisView
from worktime_tracker.views.dashboard_view import DashboardView
from worktime_tracker.views.monthly_records_view import MonthlyRecordsView
from worktime_tracker.views.records_view import RecordsView
from worktime_tracker.views.settings_view import SettingsView

NAVIGATION_UNSELECTED_COLOR = "#B0BEC5"


class WorkTimeApp(toga.App):
    def startup(self):
        data_dir = Path(self.paths.data)
        data_dir.mkdir(parents=True, exist_ok=True)
        self.db = Database(data_dir / "worktime.sqlite3")
        self.repository = WorkRecordRepository(self.db)
        self.settings_repository = SettingsRepository(self.db)
        self.ledger_repository = LedgerRepository(self.db)
        self.dashboard_view = DashboardView(self.repository, self.ledger_repository)
        self.records_view = RecordsView(
            self.repository,
            self.ledger_repository,
            self.settings_repository,
            self.refresh_views,
            self.show_calendar,
        )
        self.monthly_view = MonthlyRecordsView(
            self.repository,
            self.edit_calendar_record,
            self.ledger_repository,
            self.settings_repository,
            self.refresh_views,
        )
        self.analysis_view = AnalysisView(self.repository, self.ledger_repository)
        self.settings_view = SettingsView(
            self.settings_repository,
            self.ledger_repository,
            self.repository,
            self.refresh_views,
        )
        self.tabs = toga.OptionContainer(
            content=[
                ("首頁", self.dashboard_view.build()),
                ("紀錄", self.records_view.build()),
                ("日曆", self.monthly_view.build()),
                ("分析", self.analysis_view.build()),
                ("設定", self.settings_view.build()),
            ],
            on_select=self.on_tab_select,
            style=Pack(flex=1, color=NAVIGATION_UNSELECTED_COLOR),
        )
        self.main_window = toga.MainWindow(title=APP_NAME)
        self.main_window.content = self.tabs
        self.main_window.show()

    def refresh_views(self):
        for view in (
            self.dashboard_view,
            self.records_view,
            self.monthly_view,
            self.analysis_view,
            self.settings_view,
        ):
            view.refresh()

    def edit_calendar_record(self, record):
        """Load a calendar record and navigate to the existing record editor."""
        self.records_view.load(record)
        self.tabs.current_tab = 1

    def show_calendar(self):
        """Return to the calendar without changing its selected month."""
        self.tabs.current_tab = 2

    async def on_tab_select(self, widget):
        self.refresh_views()


def main():
    return WorkTimeApp()
