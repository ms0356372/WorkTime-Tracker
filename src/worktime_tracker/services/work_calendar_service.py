"""Single source of truth for workday classification and holiday caching."""

from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timedelta, timezone
from urllib.request import Request, urlopen

OFFICIAL_SOURCE = "行政院人事行政總處－中華民國政府行政機關辦公日曆表"
# The endpoint is injectable because the open-data resource URL can change independently
# of the app. Tests and restore never require a live network connection.
OFFICIAL_CALENDAR_URL = "https://data.gov.tw/api/v2/rest/dataset/14718"


def _parse_date(value: str) -> date:
    value = value.strip().replace("/", "")
    if len(value) == 7:  # ROC yyyMMdd
        return date(int(value[:3]) + 1911, int(value[3:5]), int(value[5:]))
    if len(value) == 8:
        return date(int(value[:4]), int(value[4:6]), int(value[6:]))
    return date.fromisoformat(value)


def parse_official_calendar_csv(payload: bytes | str) -> list[tuple[date, str]]:
    """Parse DGPA open-data CSV and return only declared holidays."""
    text = payload.decode("utf-8-sig") if isinstance(payload, bytes) else payload
    rows = csv.DictReader(io.StringIO(text))
    holidays = []
    for row in rows:
        normalized = {str(k).strip().lower(): str(v or "").strip() for k, v in row.items()}
        raw_date = normalized.get("date") or normalized.get("日期") or normalized.get("西元日期")
        holiday = normalized.get("isholiday") or normalized.get("是否放假")
        if not raw_date or holiday.lower() not in {"1", "2", "true", "yes", "是", "y"}:
            continue
        name = normalized.get("description") or normalized.get("說明") or normalized.get("備註") or "國定假日"
        holidays.append((_parse_date(raw_date), name))
    return holidays


class WorkCalendarService:
    def __init__(self, overrides, holidays, settings, fetcher=None):
        self.overrides = overrides
        self.holidays = holidays
        self.settings = settings
        self.fetcher = fetcher or self._download

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

    def get_missing_workdays(self, start: date, end: date, records) -> list[date]:
        if end < start:
            return []
        recorded = {record.work_date for record in records}
        days = (end - start).days + 1
        return [
            day
            for offset in range(days)
            if (day := start + timedelta(days=offset)) not in recorded
            and self.is_workday(day)
        ]

    def sync_year(self, year: int, url: str = OFFICIAL_CALENDAR_URL) -> bool:
        """Best-effort sync; cached data remains authoritative on any failure."""
        try:
            payload = self.fetcher(url)
            # data.gov.tw's dataset endpoint returns metadata; resolve its official
            # CSV distribution without scraping an unofficial calendar website.
            raw_bytes = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
            if raw_bytes.lstrip().startswith((b"{", b"[")):
                metadata = json.loads(raw_bytes.decode("utf-8"))
                urls = []

                def collect(value):
                    if isinstance(value, dict):
                        for child in value.values():
                            collect(child)
                    elif isinstance(value, list):
                        for child in value:
                            collect(child)
                    elif isinstance(value, str) and value.startswith("http") and ".csv" in value.lower():
                        urls.append(value)

                collect(metadata)
                candidates = [candidate for candidate in urls if str(year) in candidate] or urls
                if not candidates:
                    return False
                payload = self.fetcher(candidates[0])
            parsed = [item for item in parse_official_calendar_csv(payload) if item[0].year == year]
            if not parsed:
                return False
            self.holidays.replace_year(year, parsed, OFFICIAL_SOURCE)
            return True
        except Exception:
            return False

    @staticmethod
    def _download(url: str) -> bytes:
        request = Request(url, headers={"User-Agent": "WorkTimeTracker/0.8"})
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
