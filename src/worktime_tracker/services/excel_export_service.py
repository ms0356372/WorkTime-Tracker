"""Human-readable XLSX reports built from the application's canonical services."""

from dataclasses import replace
from datetime import date
from pathlib import Path

from worktime_tracker.models import LedgerOrigin, TransactionType
from worktime_tracker.services.analytics_service import (
    calculate_month_summary,
    calculate_year_summary,
)
from worktime_tracker.services.worktime_calculator import calculate_work_minutes
from worktime_tracker.utils.formatting import format_minutes


def export_filename(scope: str, year: int, month: int | None = None, today=None):
    if scope == "month":
        return f"工時管家_{year}-{month:02d}.xlsx"
    if scope == "year":
        return f"工時管家_{year}年度.xlsx"
    return f"工時管家_全部紀錄_{(today or date.today()):%Y%m%d}.xlsx"


def _setting(settings, key, default=""):
    if hasattr(settings, "get"):
        return settings.get(key, default)
    return default


def _selected(records, scope, year, month):
    if scope == "all":
        return list(records)
    if scope == "month":
        return [
            r
            for r in records
            if r.work_date.year == year and r.work_date.month == month
        ]
    return [r for r in records if r.work_date.year == year]


def export_xlsx(path, records, ledger, settings, year=None, month=None, scope=None):
    """Write a four-sheet XLSX report; this file is never accepted for restore."""
    try:
        import xlsxwriter
    except ModuleNotFoundError:
        from worktime_tracker.utils import minimal_xlsxwriter as xlsxwriter

    year = year or date.today().year
    scope = scope or ("month" if month is not None else "year")
    selected = _selected(records, scope, year, month)
    if not selected:
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
            "上班時間",
            "下班時間",
            "午休扣除",
            "實際工時",
            "超時",
            "不足",
            "備註",
        ],
    )
    for row, record in enumerate(selected, 1):
        actual = calculate_work_minutes(record)
        raw = calculate_work_minutes(replace(record, deduct_break=False))
        difference = actual - record.standard_minutes
        daily.write_row(
            row,
            0,
            [
                record.work_date.strftime("%Y/%m/%d"),
                record.clock_in,
                record.clock_out,
                format_minutes(raw - actual),
                format_minutes(actual),
                format_minutes(max(difference, 0)),
                format_minutes(max(-difference, 0)),
                record.note,
            ],
        )

    summary = worksheet("統計摘要", ["項目", "值", "出勤天數", "超時", "不足"])
    comp, annual = (
        (ledger[-1].comp_balance, ledger[-1].annual_balance) if ledger else (0, 0)
    )
    if scope == "month":
        result = calculate_month_summary(records, year, month)
        rows = [
            ["統計期間", f"{year} 年 {month} 月", "", "", ""],
            [
                "總工時",
                format_minutes(result.work_minutes),
                result.workdays,
                format_minutes(result.overtime_minutes),
                format_minutes(result.shortfall_minutes),
            ],
            ["平均每日工時", format_minutes(result.average_minutes), "", "", ""],
        ]
    elif scope == "year":
        rows = []
        for selected_month in range(1, 13):
            result = calculate_month_summary(records, year, selected_month)
            rows.append(
                [
                    f"{selected_month} 月",
                    format_minutes(result.work_minutes),
                    result.workdays,
                    format_minutes(result.overtime_minutes),
                    format_minutes(result.shortfall_minutes),
                ]
            )
        annual_result = calculate_year_summary(records, year)
        rows.append(
            [
                "年度總計",
                format_minutes(annual_result.work_minutes),
                annual_result.workdays,
                format_minutes(annual_result.overtime_minutes),
                format_minutes(annual_result.shortfall_minutes),
            ]
        )
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
    row = 6
    for entry in ledger:
        if entry.ledger_origin != LedgerOrigin.MANUAL or entry.transaction_type not in {
            TransactionType.LEAVE_CONVERSION,
            TransactionType.REVERSAL,
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
            "年度特休總時數",
            format_minutes(
                int(_setting(settings, "annual_leave_total_minutes", "0") or 0)
            ),
        ),
        ("特休結算日", _setting(settings, "annual_leave_settlement_date", "")),
    ]
    for row, values in enumerate(config_rows, 1):
        config.write_row(row, 0, values)
    workbook.close()
    return Path(path)
