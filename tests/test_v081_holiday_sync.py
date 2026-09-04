"""v0.8.2 semantic selection, fallback, and TLS diagnostic regressions."""

import asyncio
import json
import threading
from datetime import date
from urllib.error import URLError

import pytest

from worktime_tracker.database import (
    CalendarOverrideRepository,
    Database,
    OfficialHolidayRepository,
    SettingsRepository,
)
from worktime_tracker.services.work_calendar_service import (
    ONLINE_SOURCE,
    PACKAGED_SOURCE,
    OfficialCalendarParseError,
    WorkCalendarService,
    parse_official_calendar_csv,
    select_official_calendar_resource,
)


def metadata_fixture():
    return {
        "result": {
            "resource": [
                {
                    "resourceDescription": "115年 Google 行事曆專用",
                    "resourceFormat": "CSV",
                    "resourceDownloadUrl": "https://example.gov/google",
                },
                {
                    "resourceDescription": "115年中華民國政府行政機關辦公日曆表",
                    "resourceFormat": "CSV",
                    "resourceDownloadUrl": "https://example.gov/uploaded/2025/abc123",
                },
                {
                    "resourceDescription": "115年辦公日曆 PDF",
                    "resourceFormat": "PDF",
                    "resourceDownloadUrl": "https://example.gov/pdf",
                },
                {
                    "resourceDescription": "116年度政府機關辦公日曆資料",
                    "resourceFormat": "csv",
                    "resourceDownloadUrl": "https://example.gov/resource/no-extension",
                },
                {
                    "resourceDescription": "116年辦公日曆 ODS",
                    "resourceFormat": "ODS",
                    "resourceDownloadUrl": "https://example.gov/ods",
                },
            ]
        }
    }


def service(tmp_path):
    db = Database(tmp_path / "holiday.db")
    return db, WorkCalendarService(
        CalendarOverrideRepository(db),
        OfficialHolidayRepository(db),
        SettingsRepository(db),
    )


def test_resource_selection_uses_roc_description_and_format_not_url():
    metadata = metadata_fixture()
    selected_2026 = select_official_calendar_resource(metadata, 2026)
    selected_2027 = select_official_calendar_resource(metadata, 2027)
    assert selected_2026.download_url.endswith("/2025/abc123")
    assert selected_2027.download_url.endswith("/no-extension")
    assert selected_2026.format == "CSV"
    assert "Google" not in selected_2026.description


def test_parser_validates_headers_and_only_accepts_holiday_flag_two():
    payload = b"\xef\xbb\xbf" + "西元日期,星期,是否放假,備註\n20260101,四,2,開國紀念日\n20260102,五,0,上班\n".encode()
    assert parse_official_calendar_csv(payload) == [(date(2026, 1, 1), "開國紀念日")]
    with pytest.raises(OfficialCalendarParseError, match="缺少"):
        parse_official_calendar_csv("日期,備註\n20260101,錯誤")


def test_empty_database_loads_packaged_2026_and_2027_without_network(tmp_path):
    db, calendar = service(tmp_path)
    loaded = calendar.ensure_packaged_fallback()
    assert loaded[2026] > 0 and loaded[2027] > 0
    assert OfficialHolidayRepository(db).for_year(2026)[0]["source"] == PACKAGED_SOURCE
    assert OfficialHolidayRepository(db).for_year(2027)[0]["source"] == PACKAGED_SOURCE
    assert calendar.day_type(date(2026, 1, 1)) == "國定假日"


def test_online_sync_replaces_packaged_cache_and_url_year_is_irrelevant(tmp_path):
    db, calendar = service(tmp_path)
    calendar.ensure_packaged_fallback()
    metadata = json.dumps(metadata_fixture(), ensure_ascii=False).encode()
    csv_payload = "西元日期,是否放假,備註\n20261009,2,線上更新假日\n".encode()
    calendar.fetcher = lambda url: metadata if url.endswith("14718") else csv_payload
    result = calendar.sync_year(2026)
    assert result.success and result.holiday_count == 1
    row = OfficialHolidayRepository(db).get(date(2026, 10, 9))
    assert row["source"] == ONLINE_SOURCE and row["name"] == "線上更新假日"


def test_network_failure_reports_reason_and_preserves_existing_cache(tmp_path):
    db, calendar = service(tmp_path)
    calendar.ensure_packaged_fallback()
    before = [dict(row) for row in OfficialHolidayRepository(db).for_year(2027)]
    calendar.fetcher = lambda url: (_ for _ in ()).throw(URLError("offline"))
    result = calendar.sync_year(2027)
    assert not result.success
    assert result.error_code == "NETWORK_ERROR"
    assert "網路連線失敗" in result.error_message
    after = [dict(row) for row in OfficialHolidayRepository(db).for_year(2027)]
    assert after == before


def test_each_year_sync_is_independent_on_partial_success(tmp_path):
    db, calendar = service(tmp_path)
    calendar.ensure_packaged_fallback()
    metadata = json.dumps(metadata_fixture(), ensure_ascii=False).encode()

    def fetch(url):
        if url.endswith("14718"):
            return metadata
        if url.endswith("abc123"):
            return "西元日期,是否放假,備註\n20260101,2,線上元旦\n"
        raise URLError("2027 timeout")

    calendar.fetcher = fetch
    result_2026 = calendar.sync_year(2026)
    before_2027 = [dict(row) for row in OfficialHolidayRepository(db).for_year(2027)]
    result_2027 = calendar.sync_year(2027)
    assert result_2026.success and not result_2027.success
    assert OfficialHolidayRepository(db).for_year(2026)[0]["source"] == ONLINE_SOURCE
    assert [dict(row) for row in OfficialHolidayRepository(db).for_year(2027)] == before_2027


def test_missing_holiday_data_skips_unsafe_missing_day_deduction(tmp_path):
    _, calendar = service(tmp_path)
    assert calendar.get_missing_workdays(
        date(2028, 1, 3), date(2028, 1, 3), []
    ) == []


def test_resource_not_found_and_year_mismatch_have_actionable_diagnostics(tmp_path):
    _, calendar = service(tmp_path)
    wrong_metadata = {
        "result": {
            "resource": [
                {
                    "resourceDescription": "114年辦公日曆",
                    "resourceFormat": "CSV",
                    "resourceDownloadUrl": "https://example.gov/opaque",
                }
            ]
        }
    }
    calendar.fetcher = lambda url: json.dumps(wrong_metadata, ensure_ascii=False)
    missing = calendar.sync_year(2026)
    assert missing.error_code == "RESOURCE_NOT_FOUND"
    assert "民國115年" in missing.error_message

    metadata = json.dumps(metadata_fixture(), ensure_ascii=False)
    calendar.fetcher = lambda url: (
        metadata
        if url.endswith("14718")
        else "西元日期,是否放假,備註\n20250101,2,錯誤年度\n"
    )
    mismatch = calendar.sync_year(2026)
    assert mismatch.error_code == "YEAR_MISMATCH"
    assert "不包含 2026 年" in mismatch.error_message


def test_ssl_certificate_error_is_not_reported_as_generic_network(tmp_path):
    import ssl

    _, calendar = service(tmp_path)
    calendar.fetcher = lambda url: (_ for _ in ()).throw(
        ssl.SSLCertVerificationError("Missing Subject Key Identifier")
    )
    result = calendar.sync_year(2026)
    assert result.error_code == "SSL_CERTIFICATE_ERROR"
    assert result.error_message == "安全連線驗證失敗：無法驗證政府資料網站的安全憑證。"


def test_sync_years_are_previous_then_current_gregorian_year():
    from worktime_tracker.services.work_calendar_service import holiday_sync_years

    assert holiday_sync_years(date(2026, 9, 3)) == (2025, 2026)
    assert holiday_sync_years(date(2027, 1, 1)) == (2026, 2027)


def test_worker_fetch_does_not_write_repository(tmp_path):
    db, calendar = service(tmp_path)
    metadata = json.dumps(metadata_fixture(), ensure_ascii=False).encode()
    csv_payload = "西元日期,是否放假,備註\n20260101,2,線上元旦\n".encode()
    calendar.fetcher = lambda url: metadata if url.endswith("14718") else csv_payload
    original_replace = calendar.holidays.replace_year
    worker_thread = None

    def reject_worker_write(*args, **kwargs):
        assert threading.current_thread() is threading.main_thread()
        return original_replace(*args, **kwargs)

    calendar.holidays.replace_year = reject_worker_write

    async def fetch_in_worker():
        nonlocal worker_thread

        def fetch():
            nonlocal worker_thread
            worker_thread = threading.current_thread()
            return calendar.fetch_year_data(2026)

        return await asyncio.to_thread(fetch)

    downloaded = asyncio.run(fetch_in_worker())
    assert worker_thread is not threading.main_thread()
    assert downloaded.success
    assert OfficialHolidayRepository(db).for_year(2026) == []

    saved = calendar.save_year_data(downloaded)
    assert saved.success
    assert OfficialHolidayRepository(db).get(date(2026, 1, 1))["source"] == ONLINE_SOURCE
