"""Cross-platform Briefcase build driver with durable console/file logging."""
from __future__ import annotations
import hashlib
import importlib.metadata
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from src.worktime_tracker.config import APP_VERSION, BUILD_SIZE_WARNING_MB

ROOT = Path(__file__).parent
RELEASE = ROOT / "release"

class Tee:
    """Write build output to the terminal and a persistent UTF-8 log."""
    def __init__(self, *streams): self.streams = streams
    def write(self, value):
        for stream in self.streams: stream.write(value); stream.flush()
        return len(value)
    def flush(self):
        for stream in self.streams: stream.flush()

def enable_logging() -> object:
    RELEASE.mkdir(exist_ok=True)
    log = (RELEASE / "android_build.log").open("w", encoding="utf-8")
    sys.stdout = Tee(sys.__stdout__, log)
    sys.stderr = Tee(sys.__stderr__, log)
    print(f"Build started: {datetime.now(timezone.utc).isoformat()}", flush=True)
    return log

def command(args: list[str]) -> None:
    print("+", subprocess.list2cmdline(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)

def artifacts() -> list[Path]:
    build = ROOT / "build"
    return [path for path in build.rglob("*") if path.suffix.lower() in {".apk", ".aab", ".ipa"}] if build.exists() else []

def version(name: str) -> str:
    try: return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError: return "not installed"

def report(test: str, build: str, artifact: Path | None = None, error: str = "") -> None:
    size = artifact.stat().st_size if artifact else 0
    sha = hashlib.sha256(artifact.read_bytes()).hexdigest() if artifact else "N/A"
    (RELEASE / "build_report.txt").write_text(
        f"APP Version: {APP_VERSION}\nBuild Date: {datetime.now(timezone.utc).isoformat()}\n"
        f"Python Version: {platform.python_version()}\nBriefcase Version: {version('briefcase')}\n"
        f"Toga Version: {version('toga')}\nPlatform: {platform.platform()}\nTests: {test}\n"
        f"Build: {build}\nArtifact: {artifact or 'N/A'}\nFile Size: {size/1048576:.2f} MB\n"
        f"SHA256: {sha}\nError: {error or 'N/A'}\n", encoding="utf-8")
    (RELEASE / "dependency_report.txt").write_text(
        "Runtime: toga（GUI，使用中）\nRuntime: XlsxWriter（Excel 輸出，使用中）\n"
        "Build only: briefcase\nDevelopment only: pytest, ruff\n", encoding="utf-8")
    if size / 1048576 > BUILD_SIZE_WARNING_MB:
        print("APP 檔案偏大，請檢查是否存在非必要 dependency 或 asset。", flush=True)

def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ("all" if platform.system() == "Darwin" else "android")
    if action not in {"android", "ios", "all", "test", "clean"}:
        print("用法：python build_mobile.py android|ios|all|test|clean")
        return 2
    if action == "clean":
        shutil.rmtree(ROOT / "build", ignore_errors=True)
        print("已清除 build 目錄。")
        return 0
    test_status = "FAIL"
    try:
        print("[TEST] 執行完整測試", flush=True)
        command([sys.executable, "-m", "pytest", "-q"])
        test_status = "PASS"
        if action == "test":
            report(test_status, "SKIPPED")
            return 0
        targets = ["android"] if action == "android" else ["iOS"] if action == "ios" else ["android", "iOS"]
        if "iOS" in targets and platform.system() != "Darwin":
            print("iOS 需要 macOS + Xcode，已跳過。", flush=True)
            targets.remove("iOS")
        for target in targets:
            print(f"[CREATE] 建立／更新 {target} 專案", flush=True)
            command([sys.executable, "-m", "briefcase", "create", target])
            print(f"[BUILD] 編譯 {target}", flush=True)
            command([sys.executable, "-m", "briefcase", "build", target])
            print(f"[PACKAGE] 打包 {target}", flush=True)
            command([sys.executable, "-m", "briefcase", "package", target])
        found = sorted(artifacts(), key=lambda path: path.stat().st_mtime)
        if not found:
            raise RuntimeError("Briefcase 執行完成，但找不到 APK、AAB 或 IPA artifact。")
        artifact = found[-1]
        destination = RELEASE / ("android" if artifact.suffix.lower() in {".apk", ".aab"} else "ios")
        destination.mkdir(parents=True, exist_ok=True)
        artifact = Path(shutil.copy2(artifact, destination / artifact.name))
        report(test_status, "PASS", artifact)
        print(f"建置成功：{artifact}", flush=True)
        return 0
    except Exception as exc:
        report(test_status, "FAIL", error=str(exc))
        print(f"建置失敗：{exc}", file=sys.stderr, flush=True)
        return 1

if __name__ == "__main__":
    log_handle = enable_logging()
    try:
        exit_code = main()
    finally:
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        log_handle.close()
    raise SystemExit(exit_code)
