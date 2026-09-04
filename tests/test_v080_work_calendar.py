"""v0.8 calendar classification, missing-day ledger, cache and migration tests."""

from datetime import date

from worktime_tracker.database import (
    CalendarOverrideRepository,
    Database,
    LedgerRepository,
    OfficialHolidayRepository,
    SettingsRepository,
    WorkRecordRepository,
)
from worktime_tracker.models import DeductionPriority, TransactionType, WorkRecord
from worktime_tracker.services.balance_service import LeaveBalanceService
from worktime_tracker.services.work_calendar_service import (
    WorkCalendarService,
    parse_official_calendar_csv,
)
from worktime_tracker.services.worktime_calculator import calculate_work_minutes
from worktime_tracker.services.record_service import WorkRecordService
from worktime_tracker.services.analytics_service import calculate_month_summary


def calendar(tmp_path, standard="480"):
    db = Database(tmp_path / "calendar.db")
    settings = SettingsRepository(db)
    settings.set("daily_standard_minutes", standard)
    service = WorkCalendarService(
        CalendarOverrideRepository(db), OfficialHolidayRepository(db), settings
    )
    service.ensure_packaged_fallback()
    return db, settings, service


def test_classification_priority_weekends_holidays_and_overrides(tmp_path):
    db, _, service = calendar(tmp_path)
    holidays = OfficialHolidayRepository(db)
    overrides = CalendarOverrideRepository(db)
    monday = date(2026, 9, 7)
    saturday = date(2026, 9, 5)
    assert service.standard_minutes_for(monday) == 480
    assert service.standard_minutes_for(saturday) == 0
    holidays.replace_year(2026, [(monday, "中秋節")], "fixture")
    assert service.day_type(monday) == "國定假日"
    assert service.standard_minutes_for(monday) == 0
    overrides.save(monday, "WORKDAY", "公司補班")
    overrides.save(saturday, "WORKDAY", "公司補班")
    assert service.standard_minutes_for(monday) == 480
    assert service.standard_minutes_for(saturday) == 480
    overrides.save(monday, "NON_WORKDAY", "公司休假")
    assert service.standard_minutes_for(monday) == 0


def test_missing_days_exclude_today_future_weekends_and_before_start(tmp_path):
    _, _, service = calendar(tmp_path)
    # 2026-09-08 and 09 are the only past weekdays in the tracking range.
    missing = service.get_missing_workdays(
        date(2026, 9, 8), date(2026, 9, 9), []
    )
    assert missing == [date(2026, 9, 8), date(2026, 9, 9)]
    entries = LeaveBalanceService().recalculate_balances(
        [],
        annual_opening=4800,
        comp_opening=180,
        priority=DeductionPriority.COMP_TIME_FIRST,
        calendar=service,
        tracking_start_date=date(2026, 9, 8),
        today=date(2026, 9, 10),
    )
    missing_entries = [e for e in entries if e.transaction_type == TransactionType.MISSING_WORKDAY_DEDUCTION]
    assert len(missing_entries) == 2
    assert all(e.source_record_id is None for e in missing_entries)
    assert (missing_entries[0].comp_change, missing_entries[0].annual_change) == (-180, -300)


def test_weekend_and_holiday_work_earn_all_actual_minutes_with_lunch(tmp_path):
    db, _, service = calendar(tmp_path)
    OfficialHolidayRepository(db).replace_year(
        2026, [(date(2026, 10, 9), "國慶日補假")], "fixture"
    )
    records = [
        WorkRecord(date(2026, 9, 5), "08:00", "13:00", deduct_break=False),
        WorkRecord(date(2026, 10, 9), "08:00", "17:00", break_start="12:00", break_end="12:30"),
    ]
    assert [calculate_work_minutes(r) for r in records] == [300, 510]
    entries = LeaveBalanceService().recalculate_balances(records, calendar=service, today=date(2026, 10, 10))
    assert [e.comp_change for e in entries] == [300, 510]


def test_official_csv_parser_cache_and_offline_fallback(tmp_path):
    payload = "西元日期,星期,是否放假,備註\n20260928,一,2,教師節\n20260929,二,0,上班\n".encode()
    assert parse_official_calendar_csv(payload) == [(date(2026, 9, 28), "教師節")]
    db, _, service = calendar(tmp_path)
    metadata = b'{"result":{"resource":[{"resourceDescription":"115 year office calendar","resourceFormat":"CSV","resourceDownloadUrl":"https://example.invalid/calendar"}]}}'.replace(
        b"115 year", "115年".encode()
    )
    service.fetcher = lambda url: metadata if url.endswith("14718") else payload
    assert service.sync_year(2026)
    assert OfficialHolidayRepository(db).get(date(2026, 9, 28))["name"] == "教師節"
    service.fetcher = lambda url: (_ for _ in ()).throw(TimeoutError())
    assert not service.sync_year(2026)
    assert service.day_type(date(2026, 9, 28)) == "國定假日"


def test_official_dataset_metadata_resolves_csv_without_live_network(tmp_path):
    db, _, service = calendar(tmp_path)
    calls = []

    def fixture_fetch(url):
        calls.append(url)
        if url.endswith("14718"):
            return b'{"result":{"distribution":[{"resourceDescription":"115 year calendar", "resourceFormat":"CSV", "downloadURL":"https://example.invalid/resource/abc"}]}}'.replace(b"115 year", "115年".encode())
        return "西元日期,是否放假,備註\n20261009,2,國慶日補假\n"

    service.fetcher = fixture_fetch
    assert service.sync_year(2026)
    assert calls == [
        "https://data.gov.tw/api/v2/rest/dataset/14718",
        "https://example.invalid/resource/abc",
    ]
    assert OfficialHolidayRepository(db).get(date(2026, 10, 9))["name"] == "國慶日補假"


def test_tracking_start_migration_defaults_to_today_without_history_replay(tmp_path):
    chosen_today = date(2026, 9, 3)
    db = Database(
        tmp_path / "migration.db",
        today_provider=lambda: chosen_today,
    )
    settings = SettingsRepository(db)
    assert settings.tracking_start_date(chosen_today) == chosen_today
    assert settings.get("work_tracking_start_date") == "2026-09-03"
    service = WorkCalendarService(CalendarOverrideRepository(db), OfficialHolidayRepository(db), settings)
    entries = LeaveBalanceService().recalculate_balances(
        WorkRecordRepository(db).all(), calendar=service,
        tracking_start_date=chosen_today, today=chosen_today,
    )
    assert not entries


def test_rebuild_is_deterministic_for_missing_workday(tmp_path):
    db, settings, service = calendar(tmp_path)
    settings.set("work_tracking_start_date", "2026-09-07")
    repo, ledger = WorkRecordRepository(db), LedgerRepository(db)
    for _ in range(10):
        ledger.rebuild_for_records(
            LeaveBalanceService(), repo.all(), calendar=service,
            tracking_start_date=date(2026, 9, 7), today=date(2026, 9, 8),
        )
    events = ledger.all()
    assert len(events) == 1
    assert events[0].transaction_type == TransactionType.MISSING_WORKDAY_DEDUCTION
    assert events[0].annual_change == -480


def test_deleting_yesterdays_record_creates_missing_event(tmp_path):
    db, settings, calendar_service = calendar(tmp_path)
    settings.set("work_tracking_start_date", "2026-09-07")
    records, ledger = WorkRecordRepository(db), LedgerRepository(db)
    service = WorkRecordService(
        records, ledger, settings, calendar_service,
        today_provider=lambda: date(2026, 9, 8),
    )
    record = WorkRecord(date(2026, 9, 7), "08:00", "17:00")
    service.save(record)
    service.delete(record.id)
    event = ledger.all()[0]
    assert event.transaction_type == TransactionType.MISSING_WORKDAY_DEDUCTION
    assert event.source_record_id is None
    assert event.annual_change == -480


def test_month_analysis_includes_missing_shortfall_not_attendance(tmp_path):
    _, _, service = calendar(tmp_path)
    summary = calculate_month_summary(
        [], 2026, 9, service, date(2026, 9, 9), date(2026, 9, 7)
    )
    assert summary.work_minutes == 0
    assert summary.workdays == 0
    assert summary.shortfall_minutes == 960
