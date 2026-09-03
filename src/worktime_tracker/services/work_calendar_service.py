"""Workday classification and resilient Taiwan official-holiday synchronization."""

from __future__ import annotations

import csv
import io
import json
import socket
import traceback
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from importlib.resources import files
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OFFICIAL_SOURCE = "行政院人事行政總處－中華民國政府行政機關辦公日曆表"
OFFICIAL_CALENDAR_URL = "https://data.gov.tw/api/v2/rest/dataset/14718"
PACKAGED_SOURCE = "DGPA_PACKAGED"
ONLINE_SOURCE = "DGPA_ONLINE"


class OfficialCalendarError(RuntimeError):
    code = "UNKNOWN_ERROR"


class OfficialCalendarMetadataError(OfficialCalendarError):
    code = "METADATA_PARSE_ERROR"


class OfficialCalendarResourceNotFound(OfficialCalendarError):
    code = "RESOURCE_NOT_FOUND"


class OfficialCalendarParseError(OfficialCalendarError):
    code = "CSV_PARSE_ERROR"


class OfficialCalendarYearMismatch(OfficialCalendarError):
    code = "YEAR_MISMATCH"


@dataclass(frozen=True)
class OfficialCalendarResource:
    description: str
    format: str
    download_url: str


@dataclass(frozen=True)
class HolidaySyncResult:
    success: bool
    year: int
    holiday_count: int = 0
    source: str | None = None
    resource_description: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    def __bool__(self) -> bool:
        return self.success


def _parse_date(value: str) -> date:
    value = value.strip().replace("/", "")
    if len(value) == 7:  # ROC yyyMMdd
        return date(int(value[:3]) + 1911, int(value[3:5]), int(value[5:]))
    if len(value) == 8:
        return date(int(value[:4]), int(value[4:6]), int(value[6:]))
    return date.fromisoformat(value)


def _resource_collection(metadata: object) -> list[dict]:
    """Read only documented resource collections, with small schema aliases."""
    if not isinstance(metadata, dict):
        raise OfficialCalendarMetadataError("政府資料集 Metadata 格式無效。")
    result = metadata.get("result", metadata)
    if isinstance(result, list):
        resources = result
    elif isinstance(result, dict):
        resources = next(
            (
                result[key]
                for key in ("resource", "resources", "distribution")
                if isinstance(result.get(key), list)
            ),
            None,
        )
    else:
        resources = None
    if resources is None or not all(isinstance(item, dict) for item in resources):
        raise OfficialCalendarMetadataError("政府資料集 Metadata 缺少 resource 清單。")
    return resources


def select_official_calendar_resource(
    metadata: object, year: int
) -> OfficialCalendarResource:
    """Select an annual CSV by ROC-year description, never by its URL or filename."""
    roc_marker = f"{year - 1911}年"
    candidates: list[OfficialCalendarResource] = []
    for item in _resource_collection(metadata):
        description = str(
            item.get("resourceDescription")
            or item.get("description")
            or item.get("title")
            or ""
        ).strip()
        resource_format = str(
            item.get("resourceFormat") or item.get("format") or ""
        ).strip()
        download_url = str(
            item.get("resourceDownloadUrl")
            or item.get("downloadURL")
            or item.get("downloadUrl")
            or item.get("url")
            or ""
        ).strip()
        lowered = description.casefold()
        excluded = any(word in lowered for word in ("google", "匯入", "專用"))
        if (
            resource_format.casefold() == "csv"
            and roc_marker in description
            and download_url
            and not excluded
        ):
            candidates.append(
                OfficialCalendarResource(description, resource_format, download_url)
            )
    if not candidates:
        raise OfficialCalendarResourceNotFound(
            f"找不到民國{year - 1911}年的一般辦公日曆 CSV 資源。"
        )
    candidates.sort(key=lambda resource: ("辦公日曆" not in resource.description, len(resource.description)))
    return candidates[0]


def parse_official_calendar_csv(payload: bytes | str) -> list[tuple[date, str]]:
    """Parse DGPA UTF-8 CSV, validate its schema, and retain holiday rows only."""
    try:
        text = payload.decode("utf-8-sig") if isinstance(payload, bytes) else payload
        rows = csv.DictReader(io.StringIO(text))
        fieldnames = {str(name or "").strip().lower() for name in (rows.fieldnames or [])}
        date_fields = {"date", "日期", "西元日期"}
        holiday_fields = {"isholiday", "是否放假"}
        if not fieldnames.intersection(date_fields) or not fieldnames.intersection(holiday_fields):
            raise OfficialCalendarParseError("CSV 缺少日期或是否放假欄位。")
        holidays = []
        for row in rows:
            normalized = {
                str(key).strip().lower(): str(value or "").strip()
                for key, value in row.items()
            }
            raw_date = next((normalized[key] for key in date_fields if normalized.get(key)), None)
            holiday = next((normalized[key] for key in holiday_fields if key in normalized), "")
            if not raw_date or holiday != "2":
                continue
            name = (
                normalized.get("description")
                or normalized.get("說明")
                or normalized.get("備註")
                or "國定假日"
            )
            holidays.append((_parse_date(raw_date), name))
        return holidays
    except OfficialCalendarParseError:
        raise
    except Exception as exc:
        raise OfficialCalendarParseError(f"CSV 解析失敗：{exc}") from exc


class WorkCalendarService:
    def __init__(self, overrides, holidays, settings, fetcher=None):
        self.overrides = overrides
        self.holidays = holidays
        self.settings = settings
        self.fetcher = fetcher or self._download
        self._warned_years: set[int] = set()

    def ensure_packaged_fallback(self, years=(2026, 2027)) -> dict[int, int]:
        """Seed an empty cache from packaged snapshots; never overwrite online data."""
        loaded = {}
        for year in years:
            if self.holidays.for_year(year):
                continue
            resource = files("worktime_tracker.data").joinpath(
                f"taiwan_holidays_{year}.json"
            )
            payload = json.loads(resource.read_text(encoding="utf-8"))
            rows = [
                (date.fromisoformat(item["date"]), item["name"])
                for item in payload["holidays"]
            ]
            if rows:
                self.holidays.replace_year(year, rows, PACKAGED_SOURCE)
                loaded[year] = len(rows)
        return loaded

    def day_type(self, day: date) -> str:
        override = self.overrides.get(day)
        if override:
            return "工作日" if override["day_type"] == "WORKDAY" else "非上班日"
        holiday = self.holidays.get(day)
        if holiday:
            return "國定假日"
        return "正常上班日" if day.weekday() < 5 else "週末"

    def is_workday(self, day: date) -> bool:
        return self.day_type(day) in {"工作日", "正常上班日"}

    def standard_minutes_for(self, day: date) -> int:
        if not self.is_workday(day):
            return 0
        return int(self.settings.get("daily_standard_minutes", "480") or 480)

    def has_holiday_data(self, year: int) -> bool:
        return bool(self.holidays.for_year(year))

    def get_missing_workdays(self, start: date, end: date, records) -> list[date]:
        if end < start:
            return []
        recorded = {record.work_date for record in records}
        result = []
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            override = self.overrides.get(day)
            if not self.has_holiday_data(day.year) and override is None:
                if day.year not in self._warned_years:
                    print(
                        f"WARNING: {day.year} 國定假日資料尚未建立，跳過該年度漏登扣除。",
                        flush=True,
                    )
                    self._warned_years.add(day.year)
                continue
            if day not in recorded and self.is_workday(day):
                result.append(day)
        return result

    def sync_year(self, year: int, url: str = OFFICIAL_CALENDAR_URL) -> HolidaySyncResult:
        """Atomically replace one year only after metadata, CSV, and year validation."""
        roc_year = year - 1911
        try:
            print(f"Holiday sync: year={year}, roc_year={roc_year}, metadata={url}")
            metadata_bytes = self._fetch(url, "METADATA")
            try:
                metadata = json.loads(metadata_bytes.decode("utf-8-sig"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise OfficialCalendarMetadataError("政府資料集 Metadata 不是有效 JSON。") from exc
            resource = select_official_calendar_resource(metadata, year)
            print(
                "Holiday resource: "
                f"description={resource.description!r}, format={resource.format}, "
                f"url={resource.download_url}"
            )
            csv_bytes = self._fetch(resource.download_url, "CSV")
            print(f"Holiday CSV downloaded: {len(csv_bytes)} bytes")
            parsed = parse_official_calendar_csv(csv_bytes)
            selected = [item for item in parsed if item[0].year == year]
            print(f"Holiday CSV parsed: rows={len(parsed)}, selected={len(selected)}")
            if not selected:
                raise OfficialCalendarYearMismatch(
                    f"下載的資料不包含 {year} 年國定假日資料。"
                )
            self.holidays.replace_year(year, selected, ONLINE_SOURCE)
            print(f"Holiday cache saved: year={year}, count={len(selected)}")
            return HolidaySyncResult(
                True, year, len(selected), ONLINE_SOURCE, resource.description
            )
        except Exception as exc:
            traceback.print_exc()
            code, message = self._classify_error(exc)
            return HolidaySyncResult(False, year, error_code=code, error_message=message)

    def _fetch(self, url: str, stage: str) -> bytes:
        try:
            payload = self.fetcher(url)
            return payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
        except HTTPError as exc:
            error = OfficialCalendarError(f"政府網站回應 HTTP {exc.code}。")
            error.code = "HTTP_ERROR"
            raise error from exc
        except (TimeoutError, socket.timeout) as exc:
            error = OfficialCalendarError("連線逾時。")
            error.code = "NETWORK_TIMEOUT"
            raise error from exc
        except URLError as exc:
            error = OfficialCalendarError(f"網路連線失敗：{exc.reason}")
            error.code = "NETWORK_ERROR" if stage == "METADATA" else "CSV_DOWNLOAD_ERROR"
            raise error from exc
        except OSError as exc:
            error = OfficialCalendarError(f"網路連線失敗：{exc}")
            error.code = "NETWORK_ERROR" if stage == "METADATA" else "CSV_DOWNLOAD_ERROR"
            raise error from exc

    @staticmethod
    def _classify_error(exc: Exception) -> tuple[str, str]:
        if isinstance(exc, OfficialCalendarError):
            return exc.code, str(exc)
        return "DATABASE_ERROR", f"無法儲存國定假日資料：{exc}"

    @staticmethod
    def _download(url: str) -> bytes:
        request = Request(url, headers={"User-Agent": "WorkTimeTracker/0.8.1"})
        with urlopen(request, timeout=12) as response:
            return response.read()

    def needs_sync(self, year: int, now=None, max_age_days: int = 7) -> bool:
        rows = self.holidays.for_year(year)
        if not rows:
            return True
        stamp = datetime.fromisoformat(rows[0]["synced_at"])
        current = now or datetime.now(timezone.utc)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return current - stamp > timedelta(days=max_age_days)
