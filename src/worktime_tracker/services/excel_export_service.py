"""Human-readable XLSX reports built from the application's canonical services."""

from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from worktime_tracker.models import LedgerOrigin, TransactionType
from worktime_tracker.services.analytics_service import (
    calculate_month_summary,
    summarize,
)
from worktime_tracker.services.worktime_calculator import calculate_work_minutes
from worktime_tracker.utils.formatting import format_minutes
from worktime_tracker.utils.leave_year import get_current_cycle_range


def export_filename(scope: str, today=None, start_date=None, end_date=None):
    if scope == "leave_year":
        return f"工時管家_年度_{start_date:%Y%m%d}-{end_date:%Y%m%d}.xlsx"
    return f"工時管家_全部紀錄_{(today or date.today()):%Y%m%d}.xlsx"


def _setting(settings, key, default=""):
    if hasattr(settings, "get"):
        return settings.get(key, default)
    return default


def _selected(records, scope, start_date, end_date):
    if scope == "all":
        return list(records)
    if scope != "leave_year" or start_date is None or end_date is None:
        raise ValueError("settlement date required")
    return [r for r in records if start_date <= r.work_date <= end_date]


def export_xlsx(
    path,
    records,
    ledger,
    settings,
    scope="all",
    start_date=None,
    end_date=None,
    calendar=None,
    tracking_start_date=None,
    today=None,
):
    """Write a four-sheet XLSX report; this file is never accepted for restore."""
    try:
        import xlsxwriter
    except ModuleNotFoundError:
        from worktime_tracker.utils import minimal_xlsxwriter as xlsxwriter

    selected = _selected(records, scope, start_date, end_date)
    if not selected and not (calendar and tracking_start_date):
        raise ValueError("所選期間沒有可匯出的工時紀錄。")

    workbook = xlsxwriter.Workbook(str(Path(path)))
    header = workbook.add_format({"bold": True, "bg_color": "#D9EAF7"})

    def worksheet(name, columns):
        sheet = workbook.add_worksheet(name)
        sheet.freeze_panes(1, 0)
        sheet.autofilter(0, 0, 0, len(columns) - 1)
        sheet.write_row(0, 0, columns, header)
        sheet.set_column(0, len(columns) - 1, 16)
        return sheet

    daily = worksheet(
        "每日紀錄",
        [
            "日期",
            "日期類型",
            "狀態",
            "上班時間",
            "下班時間",
            "午休扣除",
            "實際工時",
            "標準工時",
            "超時",
            "不足",
            "備註",
        ],
    )
    report_rows = [(record.work_date, record) for record in selected]
    if calendar and tracking_start_date:
        report_end = min(
            end_date or (today or date.today()),
            (today or date.today()) - timedelta(days=1),
        )
        report_start = max(start_date or tracking_start_date, tracking_start_date)
        report_rows.extend(
            (day, None)
            for day in calendar.get_missing_workdays(report_start, report_end, selected)
        )
    report_rows.sort(key=lambda item: item[0])
    for row, (work_date, record) in enumerate(report_rows, 1):
        if record is None:
            standard = calendar.standard_minutes_for(work_date)
            daily.write_row(row, 0, [
                work_date.strftime("%Y/%m/%d"), calendar.day_type(work_date), "無紀錄",
                "", "", format_minutes(0), format_minutes(0), format_minutes(standard),
                format_minutes(0), format_minutes(standard), "",
            ])
            continue
        actual = calculate_work_minutes(record)
        raw = calculate_work_minutes(replace(record, deduct_break=False))
        standard = calendar.standard_minutes_for(record.work_date) if calendar else record.standard_minutes
        difference = actual - standard
        daily.write_row(
            row,
            0,
            [
                record.work_date.strftime("%Y/%m/%d"),
                calendar.day_type(record.work_date) if calendar else str(record.workday_type),
                "已登錄",
                record.clock_in,
                record.clock_out,
                format_minutes(raw - actual),
                format_minutes(actual),
                format_minutes(standard),
                format_minutes(max(difference, 0)),
                format_minutes(max(-difference, 0)),
                record.note,
            ],
        )

    summary = worksheet("統計摘要", ["項目", "值", "出勤天數", "超時", "不足"])
    comp, annual = (
        (ledger[-1].comp_balance, ledger[-1].annual_balance) if ledger else (0, 0)
    )
    if scope == "leave_year":
        result = summarize(selected, calendar, start_date, end_date, today)
        rows = [
            [
                "年度期間",
                f"{start_date:%Y/%m/%d} ～ {end_date:%Y/%m/%d}",
                "",
                "",
                "",
            ],
            [
                "總工時",
                format_minutes(result.work_minutes),
                result.workdays,
                format_minutes(result.overtime_minutes),
                format_minutes(result.shortfall_minutes),
            ],
            ["平均每日工時", format_minutes(result.average_minutes), "", "", ""],
        ]
        year, month = start_date.year, start_date.month
        for _ in range(12):
            monthly = calculate_month_summary(selected, year, month)
            rows.append(
                [
                    f"{year}/{month:02d}",
                    format_minutes(monthly.work_minutes),
                    monthly.workdays,
                    format_minutes(monthly.overtime_minutes),
                    format_minutes(monthly.shortfall_minutes),
                ]
            )
            month += 1
            if month == 13:
                year, month = year + 1, 1
    else:
        total = sum(calculate_work_minutes(record) for record in selected)
        rows = [["全部紀錄", format_minutes(total), len(selected), "", ""]]
    rows.extend(
        [
            ["目前補休餘額", format_minutes(comp), "", "", ""],
            ["目前特休餘額", format_minutes(annual), "", "", ""],
        ]
    )
    for row, values in enumerate(rows, 1):
        summary.write_row(row, 0, values)

    leave = worksheet("假別資料", ["日期", "類型", "來源", "目的", "分鐘數", "備註"])
    leave.write_row(
        1,
        0,
        [
            "年度特休總量",
            format_minutes(
                int(_setting(settings, "annual_leave_total_minutes", "0") or 0)
            ),
        ],
    )
    leave.write_row(2, 0, ["目前特休餘額", format_minutes(annual)])
    leave.write_row(3, 0, ["目前補休餘額", format_minutes(comp)])
    leave.write_row(
        4, 0, ["特休結算日", _setting(settings, "annual_leave_settlement_date", "")]
    )
    leave.write_row(5, 0, ["補休結算日", _setting(settings, "comp_leave_settlement_date", "")])
    row = 7
    for entry in ledger:
        if entry.transaction_type not in {
            TransactionType.LEAVE_CONVERSION,
            TransactionType.REVERSAL,
            TransactionType.ANNUAL_LEAVE_GRANT,
            TransactionType.ANNUAL_LEAVE_SETTLEMENT,
            TransactionType.COMP_LEAVE_SETTLEMENT,
        }:
            continue
        leave.write_row(
            row,
            0,
            [
                entry.entry_date.strftime("%Y/%m/%d"),
                str(entry.transaction_type),
                str(entry.source_leave_type or ""),
                str(entry.target_leave_type or ""),
                entry.source_minutes or 0,
                entry.note or entry.reason,
            ],
        )
        row += 1

    config = worksheet("設定摘要", ["項目", "值"])
    config_rows = [
        (
            "每日標準工時",
            format_minutes(
                int(_setting(settings, "daily_standard_minutes", "480") or 480)
            ),
        ),
        ("午休開始", _setting(settings, "lunch_break_start", "12:00")),
        ("午休結束", _setting(settings, "lunch_break_end", "13:00")),
        (
            "工時不足扣除順序",
            _setting(settings, "leave_deduction_priority", "COMP_TIME_FIRST"),
        ),
        (
            "本年度特休核給時數",
            format_minutes(
                int(_setting(settings, "annual_leave_total_minutes", "0") or 0)
            ),
        ),
        ("特休結算日", _setting(settings, "annual_leave_settlement_date", "")),
        ("補休結算日", _setting(settings, "comp_leave_settlement_date", "")),
    ]
    report_today = today or date.today()
    for label, key in (("目前特休年度", "annual_leave_settlement_date"), ("目前補休年度", "comp_leave_settlement_date")):
        value = _setting(settings, key, "")
        if value:
            settlement = date.fromisoformat(value)
            cycle_start, cycle_end = get_current_cycle_range(report_today, settlement.month, settlement.day)
            config_rows.append((label, f"{cycle_start:%Y/%m/%d} ～ {cycle_end:%Y/%m/%d}"))
    for row, values in enumerate(config_rows, 1):
        config.write_row(row, 0, values)
    workbook.close()
    return Path(path)
