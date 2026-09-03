"""Android Storage Access Framework intent and content resolver tests."""

import asyncio
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from worktime_tracker.services.android_file_service import (
    AndroidFileService,
    BACKUP_MIME,
    XLSX_MIME,
)


class Intent:
    ACTION_CREATE_DOCUMENT = "android.intent.action.CREATE_DOCUMENT"
    ACTION_OPEN_DOCUMENT = "android.intent.action.OPEN_DOCUMENT"
    CATEGORY_OPENABLE = "android.intent.category.OPENABLE"
    EXTRA_TITLE = "android.intent.extra.TITLE"

    def __init__(self, action):
        self.action = action
        self.categories = []
        self.mime_type = None
        self.extras = {}
        self.uri = "content://provider/document/1"

    def addCategory(self, category):
        self.categories.append(category)

    def setType(self, mime_type):
        self.mime_type = mime_type

    def putExtra(self, key, value):
        self.extras[key] = value

    def getData(self):
        return self.uri


class Output(BytesIO):
    def close(self):
        self.saved = self.getvalue()
        super().close()


class Input(BytesIO):
    def read(self, size=-1):
        if size == -1:
            value = super().read(1)
            return value[0] if value else -1
        return super().read(size)


class Resolver:
    def __init__(self):
        self.output = Output()
        self.input = Input(b"backup bytes")

    def openOutputStream(self, uri):
        assert uri.startswith("content://")
        return self.output

    def openInputStream(self, uri):
        assert uri.startswith("content://")
        return self.input


class Native:
    def __init__(self, resolver):
        self.resolver = resolver

    def getContentResolver(self):
        return self.resolver


class Impl:
    def __init__(self, result_code=1):
        self.native = Native(Resolver())
        self.result_code = result_code
        self.intents = []

    def start_activity(self, intent, on_complete):
        self.intents.append(intent)
        on_complete(self.result_code, intent)


def service(result_code=1):
    impl = Impl(result_code)
    app = SimpleNamespace(_impl=impl)
    return AndroidFileService(app, Intent, result_ok=1), impl


def test_create_document_uses_saf_mime_title_and_content_resolver():
    bridge, impl = service()
    saved = asyncio.run(bridge.save_bytes(b"xlsx bytes", "report.xlsx", XLSX_MIME))
    intent = impl.intents[0]
    assert saved is True
    assert intent.action == Intent.ACTION_CREATE_DOCUMENT
    assert intent.categories == [Intent.CATEGORY_OPENABLE]
    assert intent.mime_type == XLSX_MIME
    assert intent.extras[Intent.EXTRA_TITLE] == "report.xlsx"
    assert impl.native.resolver.output.saved == b"xlsx bytes"


def test_open_document_reads_content_uri_through_resolver():
    bridge, impl = service()
    payload = asyncio.run(bridge.open_bytes(BACKUP_MIME))
    intent = impl.intents[0]
    assert intent.action == Intent.ACTION_OPEN_DOCUMENT
    assert intent.categories == [Intent.CATEGORY_OPENABLE]
    assert intent.mime_type == BACKUP_MIME
    assert payload == b"backup bytes"


def test_cancelled_picker_is_not_an_error():
    bridge, _ = service(result_code=0)
    assert asyncio.run(bridge.save_bytes(b"data", "backup", BACKUP_MIME)) is False
    bridge, _ = service(result_code=0)
    assert asyncio.run(bridge.open_bytes(BACKUP_MIME)) is None


def test_android_flow_never_uses_toga_file_dialogs():
    root = Path(__file__).parents[1]
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (root / "src/worktime_tracker").rglob("*.py")
    )
    assert "toga.OpenFileDialog" not in source
    assert "toga.SaveFileDialog" not in source
    assert "multiselect=" not in source
