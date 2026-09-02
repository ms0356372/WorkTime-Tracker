"""Smoke tests for the Toga 0.5 data-source APIs used during startup."""

from __future__ import annotations
import importlib
import sys
import types
from pathlib import Path
from worktime_tracker.models import DeductionPriority


class ListSource(list):
    """Model Toga's supported mutation API; intentionally has no extend()."""

    extend = None


class Widget:
    def __init__(self, text="", *, items=None, value=None, children=None, **kwargs):
        self.text = text
        self.value = value
        self.children = Children(children or [])
        self._items = ListSource(items or [])

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
    ):
        setattr(toga, name, type(name, (Widget,), {}))
    toga.Box = Box
    toga.ScrollContainer = ScrollContainer
    toga.App = type("App", (), {"app": types.SimpleNamespace(main_window=object())})
    style = types.ModuleType("toga.style")
    style.Pack = lambda **kwargs: kwargs
    pack = types.ModuleType("toga.style.pack")
    pack.COLUMN = "column"
    monkeypatch.setitem(sys.modules, "toga", toga)
    monkeypatch.setitem(sys.modules, "toga.style", style)
    monkeypatch.setitem(sys.modules, "toga.style.pack", pack)


class SettingsRepository:
    def deduction_priority(self):
        return DeductionPriority.COMP_TIME_FIRST

    def get(self, key, default=None):
        return default


class LedgerRepository:
    def current_balances(self):
        return 0, 0

    def all(self):
        return []


class RecordRepository:
    def all(self):
        return []

    def recent(self, limit=7):
        return []

    def for_month(self, year, month):
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
