"""Excel report regressions for the human-readable v0.7 export."""

from datetime import date
from zipfile import ZipFile

import pytest

from worktime_tracker.models import WorkRecord
from worktime_tracker.database import CalendarOverrideRepository, Database, OfficialHolidayRepository, SettingsRepository
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
    export_xlsx(path, records, ledger, {})
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


def test_excel_leave_year_filter_and_filenames(tmp_path):
    records = [
        WorkRecord(date(2026, 6, 30), "08:00", "17:00", note="前一年度"),
        WorkRecord(date(2026, 7, 1), "08:00", "17:00", note="年度開始"),
        WorkRecord(
            date(2027, 6, 30),
            "12:15",
            "17:00",
            break_start="12:00",
            break_end="12:30",
            note="年度結束",
        ),
        WorkRecord(date(2027, 7, 1), "08:00", "17:00", note="下一年度"),
    ]
    path = tmp_path / "leave-year.xlsx"
    start, end = date(2026, 7, 1), date(2027, 6, 30)
    export_xlsx(path, records, [], {}, "leave_year", start, end)
    text = workbook_text(path)
    assert "前一年度" not in text and "下一年度" not in text
    assert "年度開始" in text and "年度結束" in text
    assert "2026/07/01 ～ 2027/06/30" in text
    assert "4 小時 30 分" in text  # Canonical calculator includes partial overlap.
    assert (
        export_filename("leave_year", start_date=start, end_date=end)
        == "工時管家_年度_20260701-20270630.xlsx"
    )
    assert (
        export_filename("all", today=date(2026, 9, 3))
        == "工時管家_全部紀錄_20260903.xlsx"
    )


def test_excel_empty_period_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="沒有可匯出"):
        export_xlsx(tmp_path / "empty.xlsx", [], [], {})


def test_leave_year_export_requires_settlement_range(tmp_path):
    records = [WorkRecord(date(2026, 9, 1), "08:00", "17:00")]
    with pytest.raises(ValueError, match="settlement date required"):
        export_xlsx(tmp_path / "missing.xlsx", records, [], {}, "leave_year")


def test_excel_includes_calendar_missing_day_and_holiday_standard(tmp_path):
    db = Database(tmp_path / "calendar.db")
    settings = SettingsRepository(db)
    from worktime_tracker.services.work_calendar_service import WorkCalendarService

    calendar = WorkCalendarService(
        CalendarOverrideRepository(db), OfficialHolidayRepository(db), settings
    )
    holiday = date(2026, 9, 7)
    OfficialHolidayRepository(db).replace_year(2026, [(holiday, "國定假日")], "fixture")
    record = WorkRecord(holiday, "08:00", "13:00", deduct_break=False, note="假日工作")
    path = tmp_path / "calendar.xlsx"
    export_xlsx(
        path, [record], [], settings, "leave_year",
        date(2026, 9, 7), date(2026, 9, 9), calendar,
        date(2026, 9, 7), date(2026, 9, 10),
    )
    text = workbook_text(path)
    assert "日期類型" in text and "標準工時" in text and "狀態" in text
    assert "國定假日" in text and "假日工作" in text
    assert "2026/09/08" in text and "2026/09/09" in text
    assert "無紀錄" in text and "8 小時 0 分" in text
