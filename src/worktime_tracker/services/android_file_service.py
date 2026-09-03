"""Android Storage Access Framework bridge for content-URI file transfer."""

from __future__ import annotations

import asyncio

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
BACKUP_MIME = "application/zip"


class FileTransferUnavailable(RuntimeError):
    """Raised when the current backend cannot launch Android activities."""


class AndroidFileService:
    def __init__(self, app, intent_class=None, result_ok=None):
        self.app = app
        if intent_class is None:
            from android.app import Activity
            from android.content import Intent

            intent_class = Intent
            result_ok = Activity.RESULT_OK
        self.Intent = intent_class
        self.result_ok = result_ok

    def create_document_intent(self, mime_type: str, filename: str):
        intent = self.Intent(self.Intent.ACTION_CREATE_DOCUMENT)
        intent.addCategory(self.Intent.CATEGORY_OPENABLE)
        intent.setType(mime_type)
        intent.putExtra(self.Intent.EXTRA_TITLE, filename)
        return intent

    def open_document_intent(self, mime_type: str):
        intent = self.Intent(self.Intent.ACTION_OPEN_DOCUMENT)
        intent.addCategory(self.Intent.CATEGORY_OPENABLE)
        intent.setType(mime_type)
        return intent

    async def _launch(self, intent):
        loop = asyncio.get_running_loop()
        completed = loop.create_future()

        def on_complete(*args):
            result_code, result_intent = args[-2:]
            if not completed.done():
                completed.set_result(
                    result_intent if result_code == self.result_ok else None
                )

        self.app._impl.start_activity(intent, on_complete=on_complete)
        return await completed

    def _resolver(self):
        native = getattr(self.app._impl, "native", None)
        if native is None:
            native = getattr(self.app._impl, "_native", None)
        if native is None or not hasattr(native, "getContentResolver"):
            raise FileTransferUnavailable("Android ContentResolver 無法使用。")
        return native.getContentResolver()

    async def save_bytes(self, payload: bytes, filename: str, mime_type: str):
        result = await self._launch(self.create_document_intent(mime_type, filename))
        if result is None:
            return False
        uri = result.getData()
        if uri is None:
            return False
        stream = self._resolver().openOutputStream(uri)
        if stream is None:
            raise OSError("無法開啟選取位置的輸出串流。")
        try:
            stream.write(payload)
            stream.flush()
        finally:
            stream.close()
        return True

    async def open_bytes(self, mime_type: str):
        result = await self._launch(self.open_document_intent(mime_type))
        if result is None:
            return None
        uri = result.getData()
        if uri is None:
            return None
        stream = self._resolver().openInputStream(uri)
        if stream is None:
            raise OSError("無法開啟選取備份的輸入串流。")
        payload = bytearray()
        try:
            while True:
                value = stream.read()
                if value == -1:
                    break
                payload.append(value & 0xFF)
        finally:
            stream.close()
        return bytes(payload)


def file_service_for(app):
    if not hasattr(getattr(app, "_impl", None), "start_activity"):
        raise FileTransferUnavailable(
            "目前平台不支援 Android Storage Access Framework。"
        )
    return AndroidFileService(app)
