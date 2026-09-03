"""Responsive four-metric home dashboard."""

from datetime import date
from pathlib import Path
import toga
from toga.style import Pack
from toga.style.pack import COLUMN
from worktime_tracker.services.analytics_service import calculate_month_summary
from worktime_tracker.services.worktime_calculator import calculate_work_minutes
from worktime_tracker.services.excel_export_service import export_filename, export_xlsx
from worktime_tracker.utils.file_dialogs import save_with_system_picker
from worktime_tracker.utils.formatting import format_minutes


class DashboardView:
    def __init__(
        self,
        repository,
        ledger_repository,
        settings_repository=None,
        export_directory=None,
    ):
        self.repository = repository
        self.ledger = ledger_repository
        self.settings = settings_repository
        self.export_directory = Path(export_directory) if export_directory else None

    def build(self):
        self.labels = {
            name: toga.Label("", style=Pack(margin_bottom=14))
            for name in ("today", "month", "comp", "annual")
        }
        today = date.today()
        self.export_scope = toga.Selection(
            items=["本月", "指定月份", "本年度", "全部紀錄"], value="本月"
        )
        self.export_year = toga.NumberInput(min=1, step=1, value=today.year)
        self.export_month = toga.NumberInput(min=1, max=12, step=1, value=today.month)
        content = toga.Box(
            children=list(self.labels.values())
            + [
                toga.Label("匯出範圍"),
                self.export_scope,
                toga.Label("年份"),
                self.export_year,
                toga.Label("月份（指定月份時使用）"),
                self.export_month,
                toga.Button("匯出 Excel", on_press=self.export_excel),
            ],
            style=Pack(direction=COLUMN, margin=16, gap=8),
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

    async def export_excel(self, widget):
        labels = {
            "本月": "month",
            "指定月份": "month",
            "本年度": "year",
            "全部紀錄": "all",
        }
        scope = labels[self.export_scope.value]
        today = date.today()
        year = (
            today.year
            if self.export_scope.value == "本月"
            else int(self.export_year.value)
        )
        month = (
            today.month
            if self.export_scope.value == "本月"
            else int(self.export_month.value)
        )
        output_dir = self.export_directory or Path(toga.App.app.paths.data) / "exports"
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = export_filename(scope, year, month, today)
        temporary = output_dir / filename
        try:
            export_xlsx(
                temporary,
                self.repository.all(),
                self.ledger.all(),
                self.settings,
                year,
                month,
                scope,
            )
            saved = await save_with_system_picker(
                toga.App.app.main_window, temporary, filename, ["xlsx"]
            )
            if saved is not None:
                await toga.App.app.main_window.dialog(
                    toga.InfoDialog("Excel 匯出完成", f"檔案：{filename}")
                )
        except Exception as exc:
            await toga.App.app.main_window.dialog(
                toga.ErrorDialog("無法匯出 Excel", str(exc))
            )
