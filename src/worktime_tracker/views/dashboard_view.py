"""Responsive four-metric home dashboard."""

from datetime import date
from pathlib import Path
import traceback
import toga
from toga.style import Pack
from toga.style.pack import COLUMN
from worktime_tracker.services.analytics_service import calculate_month_summary
from worktime_tracker.services.worktime_calculator import calculate_work_minutes
from worktime_tracker.services.excel_export_service import export_filename, export_xlsx
from worktime_tracker.services.android_file_service import XLSX_MIME, file_service_for
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
        self.export_scope = toga.Selection(
            items=["全部紀錄", "今年度"], value="全部紀錄"
        )
        content = toga.Box(
            children=list(self.labels.values())
            + [
                toga.Label("匯出範圍"),
                self.export_scope,
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
        today = date.today()
        output_dir = self.export_directory or Path(toga.App.app.paths.data) / "exports"
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            scope = "all"
            start = end = None
            if self.export_scope.value == "今年度":
                configured = self.settings.get("annual_leave_settlement_date")
                if not configured:
                    raise ValueError(
                        "請先至設定頁設定特休結算日，才能使用『今年度』匯出。"
                    )
                settlement = date.fromisoformat(configured)
                from worktime_tracker.utils.leave_year import (
                    get_current_leave_year_range,
                )

                start, end = get_current_leave_year_range(
                    today, settlement.month, settlement.day
                )
                scope = "leave_year"
            filename = export_filename(scope, today, start, end)
            temporary = output_dir / filename
            export_xlsx(
                temporary,
                self.repository.all(),
                self.ledger.all(),
                self.settings,
                scope,
                start,
                end,
            )
            saved = await file_service_for(toga.App.app).save_bytes(
                temporary.read_bytes(), filename, XLSX_MIME
            )
            if saved:
                await toga.App.app.main_window.dialog(
                    toga.InfoDialog("Excel 匯出完成", f"檔案：{filename}")
                )
        except Exception as exc:
            traceback.print_exc()
            await toga.App.app.main_window.dialog(
                toga.ErrorDialog("Excel 匯出失敗", str(exc))
            )
