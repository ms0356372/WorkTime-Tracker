"""Secure native Android and verified Python downloader regressions."""

import ssl
from pathlib import Path

import pytest

from worktime_tracker.services.android_network_service import (
    AndroidNetworkService,
    NetworkCertificateError,
    NetworkHttpError,
    NetworkTimeoutError,
    PythonHttpsDownloader,
    platform_downloader,
)


class FakeStream:
    def __init__(self, payload):
        self.values = iter(payload + b"\xff")
        self.remaining = len(payload)
        self.closed = False

    def read(self):
        if self.remaining == 0:
            return -1
        self.remaining -= 1
        return next(self.values)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, payload=b"official", status=200, failure=None):
        self.stream = FakeStream(payload)
        self.status = status
        self.failure = failure
        self.disconnected = False
        self.headers = {}

    def setConnectTimeout(self, value):
        self.connect_timeout = value

    def setReadTimeout(self, value):
        self.read_timeout = value

    def setRequestProperty(self, key, value):
        self.headers[key] = value

    def getResponseCode(self):
        if self.failure:
            raise self.failure
        return self.status

    def getInputStream(self):
        return self.stream

    def disconnect(self):
        self.disconnected = True


def test_android_native_https_returns_bytes_and_closes_resources():
    connection = FakeConnection(b"abc")
    downloader = AndroidNetworkService(lambda url: connection)
    assert downloader.download_bytes("https://data.gov.tw/test", timeout=12) == b"abc"
    assert connection.connect_timeout == connection.read_timeout == 12000
    assert connection.stream.closed and connection.disconnected
    assert downloader.backend_name == "ANDROID_NATIVE"


def test_android_native_https_classifies_timeout_http_and_certificate():
    with pytest.raises(NetworkTimeoutError):
        AndroidNetworkService(
            lambda url: FakeConnection(failure=TimeoutError("timed out"))
        ).download_bytes("https://example.gov")
    with pytest.raises(NetworkHttpError):
        AndroidNetworkService(
            lambda url: FakeConnection(status=503)
        ).download_bytes("https://example.gov")
    with pytest.raises(NetworkCertificateError, match="安全連線驗證失敗"):
        AndroidNetworkService(
            lambda url: FakeConnection(
                failure=RuntimeError("SSLHandshakeException: certificate rejected")
            )
        ).download_bytes("https://example.gov")


def test_platform_selection_prefers_android_native_not_urllib():
    assert isinstance(platform_downloader("android"), AndroidNetworkService)
    assert isinstance(platform_downloader("linux"), PythonHttpsDownloader)


def test_python_fallback_keeps_certificate_and_hostname_verification():
    context = PythonHttpsDownloader._ssl_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_source_never_disables_tls_verification():
    root = Path(__file__).parents[1] / "src/worktime_tracker"
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    forbidden = (
        "ssl._create_unverified_context",
        "ssl.CERT_NONE",
        "check_hostname = False",
        "verify=False",
    )
    assert not [token for token in forbidden if token in source]
