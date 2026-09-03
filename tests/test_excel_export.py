"""Excel report regressions for the human-readable v0.7 export."""

from datetime import date
from zipfile import ZipFile

import pytest

from worktime_tracker.models import WorkRecord
from worktime_tracker.services.balance_service import LeaveBalanceService
from worktime_tracker.services.excel_export_service import export_filename, export_xlsx


def workbook_text(path):
    with ZipFile(path) as archive:
        return "\n".join(
            archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name.endswith(".xml")
        )


def test_excel_export_has_four_readable_sheets_and_three_rows(tmp_path):
    records = [
        WorkRecord(date(2026, 9, day), "08:00", "17:00", note=f"客戶會議 {day}", id=day)
        for day in (1, 2, 3)
    ]
    ledger = LeaveBalanceService().recalculate_balances(records)
    path = tmp_path / "report.xlsx"
    export_xlsx(path, records, ledger, {}, 2026, 9, "month")
    with ZipFile(path) as archive:
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        assert (
            len(
                [
                    name
                    for name in archive.namelist()
                    if name.startswith("xl/worksheets/sheet")
                ]
            )
            == 4
        )
    assert all(
        name in workbook for name in ["每日紀錄", "統計摘要", "假別資料", "設定摘要"]
    )
    text = workbook_text(path)
    assert all(f"客戶會議 {day}" in text for day in (1, 2, 3))
    assert "8 小時 0 分" in text  # 09:00-18:00 style interval minus default lunch.


def test_excel_month_filter_and_filenames(tmp_path):
    records = [
        WorkRecord(date(2026, 8, 31), "08:00", "17:00", note="八月"),
        WorkRecord(date(2026, 9, 1), "08:00", "17:00", note="九月一"),
        WorkRecord(
            date(2026, 9, 2),
            "12:15",
            "17:00",
            break_start="12:00",
            break_end="12:30",
            note="九月二",
        ),
    ]
    path = tmp_path / "month.xlsx"
    export_xlsx(path, records, [], {}, 2026, 9, "month")
    text = workbook_text(path)
    assert "八月" not in text
    assert "九月一" in text and "九月二" in text
    assert "4 小時 30 分" in text  # Canonical calculator includes partial overlap.
    assert export_filename("month", 2026, 9) == "工時管家_2026-09.xlsx"
    assert export_filename("year", 2026) == "工時管家_2026年度.xlsx"
    assert (
        export_filename("all", 2026, today=date(2026, 9, 3))
        == "工時管家_全部紀錄_20260903.xlsx"
    )


def test_excel_empty_period_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="沒有可匯出"):
        export_xlsx(tmp_path / "empty.xlsx", [], [], {}, 2025, 3, "month")
