"""Observable Briefcase mobile build, APK collection, reports, and diagnostics."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import os
import platform
import shutil
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from src.worktime_tracker.config import APP_VERSION, BUILD_SIZE_WARNING_MB

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
RELEASE = ROOT / "release"
ANDROID_RELEASE = RELEASE / "android"
LOG_PATH = RELEASE / "build_android.log"

class Tee:
    """Mirror Python and child-process output to the console and build log."""
    def __init__(self, *streams): self.streams = streams
    def write(self, value: str) -> int:
        for stream in self.streams:
            stream.write(value)
            stream.flush()
        return len(value)
    def flush(self) -> None:
        for stream in self.streams: stream.flush()

def enable_logging():
    RELEASE.mkdir(parents=True, exist_ok=True)
    log = LOG_PATH.open("w", encoding="utf-8")
    sys.stdout = Tee(sys.__stdout__, log)
    sys.stderr = Tee(sys.__stderr__, log)
    print(f"Build started: {datetime.now(timezone.utc).isoformat()}", flush=True)
    return log

def run_command(args: list[str], *, check: bool = True) -> int:
    """Stream combined output line-by-line; never hide a long-running command."""
    print("+", subprocess.list2cmdline(args), flush=True)
    process = subprocess.Popen(
        args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="", flush=True)
    return_code = process.wait()
    if check and return_code:
        raise subprocess.CalledProcessError(return_code, args)
    return return_code

def package_version(name: str) -> str:
    try: return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError: return "not installed"

def android_scaffolds() -> list[Path]:
    """Return Briefcase Android scaffold roots containing the Gradle project."""
    if not BUILD.exists(): return []
    roots = {path.parent for path in BUILD.glob("*/android/gradle") if path.is_dir()}
    roots.update(path for path in BUILD.glob("*/android") if (path / "gradle").is_dir())
    return sorted(roots)

def clean_android() -> None:
    android_trees = sorted(path for path in BUILD.glob("*/android") if path.is_dir()) if BUILD.exists() else []
    for tree in android_trees:
        print(f"Removing Android scaffold/cache: {tree}", flush=True)
        shutil.rmtree(tree)
    shutil.rmtree(ANDROID_RELEASE, ignore_errors=True)

def find_apks() -> list[Path]:
    """Search Briefcase output recursively; no fixed Gradle output path assumptions."""
    return sorted(BUILD.rglob("*.apk"), key=lambda path: path.stat().st_mtime) if BUILD.exists() else []

def copy_apk(source: Path) -> tuple[Path, int, str, str]:
    kind = "debug" if "debug" in source.name.lower() else "release"
    destination = ANDROID_RELEASE / f"worktime-tracker-{APP_VERSION}-{kind}.apk"
    ANDROID_RELEASE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    size = destination.stat().st_size
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    print(f"APK type: {kind}")
    print(f"APK created: {destination.resolve()}")
    print(f"Size: {size / 1048576:.2f} MB")
    print(f"SHA256: {digest}")
    if size / 1048576 > BUILD_SIZE_WARNING_MB:
        print("WARNING: APK is larger than the configured size warning threshold.")
    return destination, size, digest, kind

def write_report(state: dict[str, str]) -> None:
    RELEASE.mkdir(parents=True, exist_ok=True)
    lines = [
        f"Build Date: {datetime.now(timezone.utc).isoformat()}",
        f"APP Version: {APP_VERSION}",
        f"Python Version: {platform.python_version()}",
        f"Briefcase Version: {package_version('briefcase')}",
        f"Toga Version: {package_version('toga')}",
        f"Platform: {platform.platform()}",
        f"pytest result: {state.get('tests', 'NOT RUN')}",
        f"Android create/update result: {state.get('scaffold', 'NOT RUN')}",
        f"Android build result: {state.get('build', 'NOT RUN')}",
        f"Android package result: {state.get('package', 'NOT RUN')}",
        f"APK type: {state.get('apk_type', 'N/A')}",
        f"APK path: {state.get('apk_path', 'N/A')}",
        f"APK size: {state.get('apk_size', 'N/A')}",
        f"SHA256: {state.get('sha256', 'N/A')}",
        f"Error: {state.get('error', 'N/A')}",
        f"FINAL STATUS: {state.get('final', 'FAIL')}",
    ]
    (RELEASE / "build_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

def validate_configuration() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    backend = data.get("build-system", {}).get("build-backend")
    if backend != "setuptools.build_meta":
        raise RuntimeError(f"Unsupported Python build backend: {backend!r}. Expected setuptools.build_meta.")
    app = data["tool"]["briefcase"]["app"]["worktime_tracker"]
    if "src/worktime_tracker" not in app["sources"]:
        raise RuntimeError("Briefcase sources must include src/worktime_tracker.")
    if "android" not in app:
        raise RuntimeError("Briefcase Android configuration is missing.")

def doctor() -> int:
    """Report prerequisites without rejecting Briefcase-managed Java or Android SDK."""
    validate_configuration()
    java = shutil.which("java")
    briefcase_installed = package_version("briefcase") != "not installed"
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {platform.python_version()}")
    print(f"Project root: {ROOT}")
    print(f"Virtual environment: {sys.prefix != getattr(sys, 'base_prefix', sys.prefix)} ({sys.prefix})")
    print(f"Briefcase version: {package_version('briefcase')}")
    print(f"Java availability: {java or 'not found on PATH'}")
    print(f"JAVA_HOME: {os.environ.get('JAVA_HOME', 'not set')}")
    print(f"Android SDK availability: {os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT') or 'not set'}")
    print(f"ANDROID_HOME: {os.environ.get('ANDROID_HOME', 'not set')}")
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    print(f"pyproject.toml: {(ROOT / 'pyproject.toml').is_file()}")
    print(f"Python build backend: {pyproject['build-system']['build-backend']}")
    print(f"Android scaffold: {android_scaffolds() or 'not created'}")
    print(f"Release directory: {RELEASE}")
    if java:
        print("System Java detected (Android builds require JDK 17):")
        run_command([java, "-version"], check=False)
    else:
        print("Briefcase-managed Java/Android SDK will be used when available.")
    if briefcase_installed:
        run_command([sys.executable, "-m", "briefcase", "--version"], check=False)
    else:
        print("Briefcase is not installed in this Python environment.")
    return 0

def build_android(clean: bool) -> int:
    state: dict[str, str] = {"final": "FAIL"}
    try:
        validate_configuration()
        if clean: clean_android()
        print("[TEST] Running project tests...", flush=True)
        state["tests"] = "FAIL"
        run_command([sys.executable, "-m", "pytest", "-q"])
        state["tests"] = "PASS"
        if android_scaffolds():
            print("[UPDATE] Existing Android scaffold found; running Briefcase update.", flush=True)
            state["scaffold"] = "UPDATE FAIL"
            run_command([sys.executable, "-m", "briefcase", "update", "android"])
            state["scaffold"] = "UPDATE PASS"
        else:
            print("[CREATE] No Android scaffold found; running Briefcase create once.", flush=True)
            state["scaffold"] = "CREATE FAIL"
            run_command([sys.executable, "-m", "briefcase", "create", "android"])
            state["scaffold"] = "CREATE PASS"
        print("[BUILD] Building Android application...", flush=True)
        state["build"] = "FAIL"
        run_command([sys.executable, "-m", "briefcase", "build", "android"])
        state["build"] = "PASS"
        package_started = datetime.now().timestamp()
        print("[PACKAGE] Packaging installable APK...", flush=True)
        state["package"] = "FAIL"
        run_command([sys.executable, "-m", "briefcase", "package", "android", "-p", "apk"])
        state["package"] = "PASS"
        candidates = [path for path in find_apks() if path.stat().st_mtime >= package_started - 2]
        if not candidates:
            raise RuntimeError("Android package command completed but no newly generated APK was found.")
        apk, size, digest, kind = copy_apk(candidates[-1])
        state.update(apk_type=kind, apk_path=str(apk.resolve()), apk_size=f"{size / 1048576:.2f} MB", sha256=digest, final="PASS")
        write_report(state)
        return 0
    except Exception as exc:
        state["error"] = str(exc)
        write_report(state)
        print(f"BUILD FAILED: {exc}", file=sys.stderr, flush=True)
        return 1

def ios_scaffolds() -> list[Path]:
    if not BUILD.exists(): return []
    return sorted(path for path in BUILD.glob("*/iOS") if path.is_dir())

def build_ios() -> int:
    """Retain the macOS Briefcase iOS path; signing remains an Xcode task."""
    if platform.system() != "Darwin":
        print("iOS builds require macOS and Xcode.", file=sys.stderr)
        return 1
    try:
        command = "update" if ios_scaffolds() else "create"
        run_command([sys.executable, "-m", "briefcase", command, "iOS"])
        run_command([sys.executable, "-m", "briefcase", "build", "iOS"])
        run_command([sys.executable, "-m", "briefcase", "package", "iOS"])
        return 0
    except Exception as exc:
        print(f"iOS BUILD FAILED: {exc}", file=sys.stderr)
        return 1

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WorkTime Tracker mobile build tool")
    parser.add_argument("action", choices=("android", "ios", "all", "test", "clean", "doctor"), nargs="?", default="android")
    parser.add_argument("--clean", action="store_true", help="Remove Android scaffold/cache before rebuilding")
    return parser.parse_args()

def main() -> int:
    args = parse_args()
    if args.action == "doctor": return doctor()
    if args.action == "test": return run_command([sys.executable, "-m", "pytest", "-q"], check=False)
    if args.action == "clean": clean_android(); return 0
    if args.action == "android": return build_android(args.clean)
    if args.action == "ios": return build_ios()
    if args.action == "all":
        android_result = build_android(args.clean)
        return android_result or build_ios()
    return 2

if __name__ == "__main__":
    log_handle = enable_logging()
    try: exit_code = main()
    finally:
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        log_handle.close()
    raise SystemExit(exit_code)
