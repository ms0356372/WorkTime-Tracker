"""Ten-step project verification, including Windows batch and build configuration."""
from __future__ import annotations
import compileall
import importlib
import subprocess
import sys
import tempfile
import tomllib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
MATERIAL_DEPENDENCY = "com.google.android.material:material:1.12.0"
sys.path.insert(0, str(ROOT / "src"))

def checked(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)

def main() -> int:
    results: dict[str, str] = {}
    steps = [
        ("Python Syntax", lambda: compileall.compile_dir(ROOT / "src", quiet=1) and compileall.compile_file(ROOT / "build_mobile.py", quiet=1)),
        ("Import Check", lambda: importlib.import_module("worktime_tracker.services.worktime_calculator")),
        ("Database Check", database_check),
        ("Worktime Calculator Tests", lambda: checked([sys.executable, "-m", "pytest", "-q", "tests/test_core.py"])),
        ("Leave Balance Tests", lambda: checked([sys.executable, "-m", "pytest", "-q", "tests/test_leave_conversion.py"])),
        ("Fatigue Index Tests", lambda: checked([sys.executable, "-m", "pytest", "-q", "tests/test_fatigue_analytics.py"])),
        ("Excel Export Test", excel_check),
        ("Backup / Restore Test", lambda: checked([sys.executable, "-m", "pytest", "-q", "tests/test_database_backup.py"])),
        ("Dependency Check", dependency_check),
        ("Build and Batch Configuration Check", build_configuration_check),
    ]
    for index, (label, operation) in enumerate(steps, 1):
        print(f"[{index}/10] {label}", flush=True)
        try:
            outcome = operation()
            if outcome is False: raise RuntimeError(f"{label} returned False")
            results[label] = "PASS"
        except Exception as exc:
            print(f"FAILED STEP: {index}\nERROR: {exc}\nFILE: {getattr(exc, 'filename', 'unknown')}")
            return 1
    print("=" * 24)
    print("PROJECT VERIFICATION\nTests: PASS\nDatabase: PASS\nExcel: PASS\nBackup: PASS\nAndroid Config: PASS\niOS Config: PASS\nBatch Files: PASS")
    print("=" * 24)
    return 0

def database_check() -> None:
    from worktime_tracker.database import Database
    db = Database(":memory:")
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 2

def excel_check() -> None:
    from worktime_tracker.models import WorkRecord
    from worktime_tracker.services.excel_export_service import export_xlsx
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "verify.xlsx"
        export_xlsx(output, [WorkRecord(date(2026, 1, 1), "09:00", "18:00")], [], {}, 2026)
        assert output.read_bytes()[:2] == b"PK"

def dependency_check() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = " ".join(data["project"]["dependencies"]).lower()
    assert not {"numpy", "pandas", "matplotlib", "scipy"}.intersection(dependencies.split())

def build_configuration_check() -> None:
    required = ["pyproject.toml", "build_android.bat", "scripts/build_android.bat", "scripts/build_ios.command", "scripts/check_batch_files.py"]
    missing = [path for path in required if not (ROOT / path).is_file()]
    if missing: raise RuntimeError(f"Missing build files: {missing}")
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["build-system"]["build-backend"] == "setuptools.build_meta"
    assert "setuptools>=69" in data["build-system"]["requires"]
    app = data["tool"]["briefcase"]["app"]["worktime_tracker"]
    assert "android" in app and "iOS" in app
    assert app["sources"] == ["src/worktime_tracker"]
    app_source = (ROOT / "src/worktime_tracker/app.py").read_text(encoding="utf-8")
    if "toga.OptionContainer" in app_source:
        android_dependencies = app["android"].get("build_gradle_dependencies", [])
        if MATERIAL_DEPENDENCY not in android_dependencies:
            raise RuntimeError(f"OptionContainer requires Android Gradle dependency {MATERIAL_DEPENDENCY}")
    checked([sys.executable, "scripts/check_batch_files.py"])

if __name__ == "__main__":
    raise SystemExit(main())
