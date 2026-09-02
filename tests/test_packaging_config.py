"""Regression coverage for the editable-install backend used by Windows builds."""
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[1]

def test_standard_editable_build_backend():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["build-system"]["build-backend"] == "setuptools.build_meta"
    assert "setuptools>=69" in data["build-system"]["requires"]
    assert data["tool"]["setuptools"]["packages"]["find"]["where"] == ["src"]

def test_batch_bootstraps_backend_before_editable_install():
    script = (ROOT / "scripts" / "build_android.bat").read_text(encoding="ascii")
    setuptools_install = script.index("pip install --upgrade pip setuptools wheel")
    briefcase_install = script.index('pip install --upgrade "briefcase>=0.3.20,<0.4"')
    editable_install = script.index('pip install -e ".[dev]"')
    assert setuptools_install < briefcase_install < editable_install
