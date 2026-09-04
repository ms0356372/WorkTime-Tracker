"""Secure platform HTTPS downloaders used by holiday synchronization."""

from __future__ import annotations

import socket
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class NetworkServiceError(RuntimeError):
    code = "NETWORK_ERROR"

    def __init__(self, user_message: str, *, detail: str = ""):
        super().__init__(user_message)
        self.user_message = user_message
        self.detail = detail


class NetworkTimeoutError(NetworkServiceError):
    code = "NETWORK_TIMEOUT"


class NetworkDnsError(NetworkServiceError):
    code = "DNS_ERROR"


class NetworkHttpError(NetworkServiceError):
    code = "HTTP_ERROR"


class NetworkCertificateError(NetworkServiceError):
    code = "SSL_CERTIFICATE_ERROR"


def classify_network_exception(exc: Exception) -> NetworkServiceError:
    """Normalize Python, injected-test, and bridged Java network failures."""
    reason = exc.reason if isinstance(exc, URLError) else exc
    if isinstance(reason, ssl.SSLCertVerificationError):
        return NetworkCertificateError(
            "安全連線驗證失敗：無法驗證政府資料網站的安全憑證。",
            detail=str(reason),
        )
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return NetworkTimeoutError("連線逾時。", detail=str(reason))
    if isinstance(reason, socket.gaierror):
        return NetworkDnsError("無法解析政府資料網站位址。", detail=str(reason))
    if isinstance(exc, HTTPError):
        return NetworkHttpError(
            f"政府網站回應 HTTP {exc.code}。", detail=str(exc)
        )
    return NetworkServiceError("網路連線失敗。", detail=str(reason))


class AndroidNetworkService:
    """Download through Android's URLConnection and system trust store."""

    backend_name = "ANDROID_NATIVE"

    def __init__(self, connection_factory=None):
        self.connection_factory = connection_factory or self._native_connection

    @staticmethod
    def _native_connection(url: str):
        # Rubicon Java is supplied by Briefcase's Android runtime.
        from java import jclass

        return jclass("java.net.URL")(url).openConnection()

    def download_bytes(self, url: str, timeout: int = 15) -> bytes:
        connection = None
        stream = None
        try:
            connection = self.connection_factory(url)
            timeout_ms = int(timeout * 1000)
            connection.setConnectTimeout(timeout_ms)
            connection.setReadTimeout(timeout_ms)
            connection.setRequestProperty("User-Agent", "WorkTimeTracker/0.8.5")
            connection.setRequestProperty("Accept", "application/json,text/csv,*/*")
            status = int(connection.getResponseCode())
            print(f"Android HTTPS response: status={status}, url={url}", flush=True)
            if status < 200 or status >= 300:
                raise NetworkHttpError(
                    f"政府網站回應 HTTP {status}。", detail=f"url={url}"
                )
            stream = connection.getInputStream()
            payload = bytearray()
            while True:
                value = stream.read()
                if value == -1:
                    break
                payload.append(value & 0xFF)
            return bytes(payload)
        except NetworkServiceError:
            raise
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            lowered = message.casefold()
            if "certificate" in lowered or "sslhandshake" in lowered or "certpath" in lowered:
                raise NetworkCertificateError(
                    "安全連線驗證失敗：無法驗證政府資料網站的安全憑證。",
                    detail=message,
                ) from exc
            if "timeout" in lowered:
                raise NetworkTimeoutError("連線逾時。", detail=message) from exc
            if "unknownhost" in lowered or "name or service" in lowered:
                raise NetworkDnsError("無法解析政府資料網站位址。", detail=message) from exc
            raise NetworkServiceError("網路連線失敗。", detail=message) from exc
        finally:
            if stream is not None:
                stream.close()
            if connection is not None and hasattr(connection, "disconnect"):
                connection.disconnect()

    def download_text(self, url: str, timeout: int = 15) -> str:
        return self.download_bytes(url, timeout).decode("utf-8-sig")


class PythonHttpsDownloader:
    """Verified urllib fallback for desktop and unit-test environments."""

    backend_name = "PYTHON_URLLIB"

    @staticmethod
    def _ssl_context() -> ssl.SSLContext:
        context = ssl.create_default_context()
        # Python 3.13 enables OpenSSL strict verification by default. Some otherwise
        # trusted legacy chains omit Subject Key Identifier. Remove only that strict
        # policy bit while retaining CA validation and hostname verification.
        strict = getattr(ssl, "VERIFY_X509_STRICT", 0)
        if strict:
            context.verify_flags &= ~strict
        return context

    def download_bytes(self, url: str, timeout: int = 15) -> bytes:
        request = Request(url, headers={"User-Agent": "WorkTimeTracker/0.8.5"})
        try:
            with urlopen(request, timeout=timeout, context=self._ssl_context()) as response:
                status = int(getattr(response, "status", 200))
                print(f"Python HTTPS response: status={status}, url={url}", flush=True)
                return response.read()
        except HTTPError as exc:
            raise classify_network_exception(exc) from exc
        except ssl.SSLCertVerificationError as exc:
            raise classify_network_exception(exc) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise classify_network_exception(exc) from exc
        except URLError as exc:
            raise classify_network_exception(exc) from exc
        except OSError as exc:
            raise classify_network_exception(exc) from exc

    def download_text(self, url: str, timeout: int = 15) -> str:
        return self.download_bytes(url, timeout).decode("utf-8-sig")


def platform_downloader(platform: str | None = None):
    """Select Android native TLS on Android; verified urllib everywhere else."""
    selected = (platform or sys.platform).casefold()
    return AndroidNetworkService() if selected == "android" else PythonHttpsDownloader()
