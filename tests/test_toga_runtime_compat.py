"""Smoke tests for the Toga 0.5 data-source APIs used during startup."""

from __future__ import annotations
import asyncio
import importlib
import sys
import types
from datetime import date
from pathlib import Path
from worktime_tracker.models import DeductionPriority, WorkRecord


class ListSource(list):
    """Model Toga's supported mutation API; intentionally has no extend()."""

    extend = None


class Widget:
    def __init__(
        self, text="", message=None, *, items=None, value=None, children=None, **kwargs
    ):
        self.text = text
        self.message = message
        self.value = value
        self.children = Children(children or [])
        self._items = ListSource(items or [])
        for name, item in kwargs.items():
            setattr(self, name, item)

    @property
    def items(self):
        return self._items

    @items.setter
    def items(self, values):
        self._items = ListSource(values)


class Children(list):
    def add(self, child):
        self.append(child)


class Box(Widget):
    def add(self, child):
        self.children.add(child)

    def replace(self, old_child, new_child):
        self.children[self.children.index(old_child)] = new_child


class ScrollContainer(Widget):
    def __init__(self, *, content, **kwargs):
        super().__init__(**kwargs)
        self.content = content


def install_fake_toga(monkeypatch):
    toga = types.ModuleType("toga")
    for name in (
        "Selection",
        "NumberInput",
        "DateInput",
        "Label",
        "Button",
        "TextInput",
        "TimeInput",
        "ConfirmDialog",
    ):
        setattr(toga, name, type(name, (Widget,), {}))
    toga.Box = Box
    toga.ScrollContainer = ScrollContainer
    class MainWindow:
        async def dialog(self, dialog):
            return True

    toga.App = type(
        "App", (), {"app": types.SimpleNamespace(main_window=MainWindow())}
    )
    style = types.ModuleType("toga.style")
    style.Pack = lambda **kwargs: kwargs
    pack = types.ModuleType("toga.style.pack")
    pack.COLUMN = "column"
    pack.ROW = "row"
    monkeypatch.setitem(sys.modules, "toga", toga)
    monkeypatch.setitem(sys.modules, "toga.style", style)
    monkeypatch.setitem(sys.modules, "toga.style.pack", pack)


class SettingsRepository:
    def deduction_priority(self):
        return DeductionPriority.COMP_TIME_FIRST

    def get(self, key, default=None):
        return default

    def lunch_break(self):
        return "12:00", "13:00"


class LedgerRepository:
    def current_balances(self):
        return 0, 0

    def all(self):
        return []


class RecordRepository:
    def all(self):
        return []

    def get_by_date(self, work_date):
        return next((record for record in self.all() if record.work_date == work_date), None)

    def recent(self, limit=7):
        return []

    def for_month(self, year, month):
        return []

    def records_for_month(self, year, month):
        return []


def load_view(module_name):
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def test_settings_refresh_uses_supported_toga_list_source_api(monkeypatch):
    install_fake_toga(monkeypatch)
    module = load_view("worktime_tracker.views.settings_view")
    view = module.SettingsView(SettingsRepository(), LedgerRepository())
    view.build()
    view._history_items = lambda: ["one", "two"]
    view.refresh()
    assert list(view.history.items) == ["one", "two"]
    assert isinstance(view.history.items, ListSource)


def test_all_v020_views_build_and_refresh_without_unsupported_sources(monkeypatch):
    install_fake_toga(monkeypatch)
    records = RecordRepository()
    ledger = LedgerRepository()
    settings = SettingsRepository()
    views = [
        load_view("worktime_tracker.views.dashboard_view").DashboardView(
            records, ledger
        ),
        load_view("worktime_tracker.views.records_view").RecordsView(
            records, ledger, settings
        ),
        load_view("worktime_tracker.views.monthly_records_view").MonthlyRecordsView(
            records, lambda record: None
        ),
        load_view("worktime_tracker.views.analysis_view").AnalysisView(records, ledger),
        load_view("worktime_tracker.views.settings_view").SettingsView(
            settings, ledger
        ),
    ]
    for view in views:
        assert view.build() is not None
        view.refresh()


def test_repository_has_no_list_source_extend_calls():
    root = Path(__file__).parents[1]
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in (root / "src").rglob("*.py")
    )
    assert ".items.extend(" not in source
    assert ".data.extend(" not in source


def test_records_refresh_ten_times_replaces_instead_of_stacking(monkeypatch):
    install_fake_toga(monkeypatch)
    module = load_view("worktime_tracker.views.records_view")
    records = RecordRepository()
    rows = [
        WorkRecord(date(2026, 9, day), "09:00", "18:00", id=day) for day in (1, 2, 3)
    ]
    records.recent = lambda limit=5: list(reversed(rows))[:limit]
    view = module.RecordsView(records, LedgerRepository(), SettingsRepository())
    view.build()
    form_identity = id(view.container.content)
    for _ in range(10):
        view.refresh()
    assert len(view.recent_box.children) == 3
    assert len(view.recent_records_host.children) == 1
    assert id(view.container.content) == form_identity


def test_month_views_preserve_independent_selected_months(monkeypatch):
    install_fake_toga(monkeypatch)
    records = RecordRepository()
    monthly = load_view(
        "worktime_tracker.views.monthly_records_view"
    ).MonthlyRecordsView(records, lambda record: None)
    analysis = load_view("worktime_tracker.views.analysis_view").AnalysisView(
        records, LedgerRepository()
    )
    monthly.build()
    analysis.build()
    monthly.selected_year, monthly.selected_month = 2026, 1
    analysis.selected_year, analysis.selected_month = 2025, 12
    monthly.show_previous_month()
    analysis.show_next_month()
    monthly.refresh()
    analysis.refresh()
    assert (monthly.selected_year, monthly.selected_month) == (2025, 12)
    assert (analysis.selected_year, analysis.selected_month) == (2026, 1)
    assert "2026 年度" in analysis.summary.text


def test_analysis_refresh_recalculates_the_selected_month(monkeypatch):
    install_fake_toga(monkeypatch)
    records = RecordRepository()
    records.all = lambda: [
        WorkRecord(date(2026, 8, 1), "09:00", "18:00"),
        WorkRecord(date(2026, 8, 2), "09:00", "19:00"),
        WorkRecord(date(2026, 9, 1), "09:00", "17:00"),
    ]
    view = load_view("worktime_tracker.views.analysis_view").AnalysisView(
        records, LedgerRepository()
    )
    view.build()
    view.selected_year, view.selected_month = 2026, 8
    view.refresh()
    assert "【2026 年 8 月】" in view.summary.text
    assert "總工時\n17 小時 0 分" in view.summary.text
    assert "出勤天數\n2 天" in view.summary.text
    assert "平均每日工時\n8 小時 30 分" in view.summary.text
    assert "超時\n1 小時 0 分" in view.summary.text


def _calendar_rows():
    return [
        WorkRecord(date(2026, 9, day), "08:00", "17:00", id=day)
        for day in (3, 2, 1)
    ]


def test_monthly_records_builds_three_stable_action_cards(monkeypatch):
    install_fake_toga(monkeypatch)
    records = RecordRepository()
    records.records_for_month = lambda year, month: _calendar_rows()
    module = load_view("worktime_tracker.views.monthly_records_view")
    view = module.MonthlyRecordsView(records, lambda record: None)
    view.build()

    for _ in range(10):
        view.refresh()

    assert len(view.list.children) == 3
    assert len(view.list_host.children) == 1
    first_information, first_actions = view.list.children[0].children
    assert [label.text for label in first_information.children] == [
        "09/03",
        "工時 8 小時 0 分",
    ]
    assert [button.text for button in first_actions.children] == ["修改", "刪除"]
    assert first_actions.children[0].style["background_color"] == "#1976D2"
    assert first_actions.children[1].style["background_color"] == "#D32F2F"


def test_monthly_card_edit_keeps_one_updated_card(monkeypatch):
    install_fake_toga(monkeypatch)
    records = RecordRepository()
    row = WorkRecord(date(2026, 9, 3), "08:00", "17:00", id=3)
    records.records_for_month = lambda year, month: [row]
    selected = []
    module = load_view("worktime_tracker.views.monthly_records_view")
    view = module.MonthlyRecordsView(records, selected.append)
    view.build()

    edit_button = view.list.children[0].children[1].children[0]
    edit_button.on_press(edit_button)
    row.clock_out = "18:00"
    view.refresh()

    assert selected == [row]
    assert len(view.list.children) == 1
    assert view.list.children[0].children[0].children[1].text == "工時 9 小時 0 分"


def test_monthly_card_delete_refreshes_without_the_deleted_record(monkeypatch):
    install_fake_toga(monkeypatch)
    rows = _calendar_rows()
    records = RecordRepository()
    records.records_for_month = lambda year, month: list(rows)
    module = load_view("worktime_tracker.views.monthly_records_view")
    view = module.MonthlyRecordsView(records, lambda record: None)

    class RecordService:
        def delete(self, record_id):
            rows[:] = [record for record in rows if record.id != record_id]

    view.record_service = RecordService()
    view.build()
    asyncio.run(view.delete_record(rows[1]))

    assert [
        card.children[0].children[0].text for card in view.list.children
    ] == ["09/03", "09/01"]


def test_monthly_cards_use_central_calculator_and_selected_month(monkeypatch):
    install_fake_toga(monkeypatch)
    records = RecordRepository()
    requested = []
    records.records_for_month = lambda year, month: (
        requested.append((year, month)) or _calendar_rows()
    )
    module = load_view("worktime_tracker.views.monthly_records_view")
    calculated = []
    monkeypatch.setattr(
        module,
        "calculate_work_minutes",
        lambda record: calculated.append(record.id) or 123,
    )
    view = module.MonthlyRecordsView(records, lambda record: None)
    view.selected_year, view.selected_month = 2026, 9
    view.build()

    assert requested[-1] == (2026, 9)
    assert calculated == [3, 2, 1]
    assert view.list.children[0].children[0].children[1].text == "工時 2 小時 3 分"
