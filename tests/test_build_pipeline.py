from pathlib import Path
import importlib.util
import zipfile


def load_build_mobile():
    spec = importlib.util.spec_from_file_location(
        "build_mobile", Path(__file__).parents[1] / "build_mobile.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_batch_sources_are_ascii_crlf_and_clean():
    from scripts.check_batch_files import iter_batch_files, validate_batch_file

    files = list(iter_batch_files())
    assert files and all(not validate_batch_file(path) for path in files)


def test_batch_source_discovery_ignores_virtual_environments(tmp_path, monkeypatch):
    from scripts import check_batch_files

    monkeypatch.setattr(check_batch_files, "ROOT", tmp_path)
    source = tmp_path / "build.cmd"
    source.write_bytes(b"@echo off\r\necho %~dp0\r\n")
    generated = tmp_path / ".venv" / "Scripts" / "activate.bat"
    generated.parent.mkdir(parents=True)
    generated.write_bytes(b"generated\n")
    assert list(check_batch_files.iter_batch_files()) == [source]


def test_apk_search_is_recursive(tmp_path, monkeypatch):
    module = load_build_mobile()
    monkeypatch.setattr(module, "BUILD", tmp_path)
    apk = tmp_path / "deep" / "outputs" / "app-debug.apk"
    apk.parent.mkdir(parents=True)
    apk.write_bytes(b"apk")
    assert module.find_apks() == [apk]
    assert module.find_apks("-debug") == [apk]


def test_debug_build_artifact_naming():
    module = load_build_mobile()
    assert module.artifact_name("debug") == "工時管家-0.1.0-debug.apk"
    assert module.artifact_name("release") == "工時管家-0.1.0-release-unsigned.apk"
    assert module.artifact_name("release", signed=True) == "工時管家-0.1.0-release.apk"


def test_unsigned_release_is_not_installable(tmp_path, monkeypatch):
    module = load_build_mobile()
    monkeypatch.setattr(module, "find_android_tool", lambda name: None)
    apk = tmp_path / "app-release-unsigned.apk"
    with zipfile.ZipFile(apk, "w") as archive:
        archive.writestr("AndroidManifest.xml", b"manifest")
        archive.writestr("classes.dex", b"dex")
        archive.writestr("lib/arm64-v8a/libapp.so", b"lib")
    result = module.inspect_apk(apk)
    assert result.complete
    assert not result.signed
    assert not module.is_installable(result)
    assert result.signature_verification == "SIGNATURE VERIFY TOOL NOT AVAILABLE"


def test_signed_complete_apk_is_installable_without_verifier(tmp_path, monkeypatch):
    module = load_build_mobile()
    monkeypatch.setattr(module, "find_android_tool", lambda name: None)
    apk = tmp_path / "app-debug.apk"
    with zipfile.ZipFile(apk, "w") as archive:
        archive.writestr("AndroidManifest.xml", b"manifest")
        archive.writestr("classes.dex", b"dex")
        archive.writestr("META-INF/CERT.SF", b"signature metadata")
        archive.writestr("META-INF/CERT.RSA", b"certificate")
    result = module.inspect_apk(apk)
    assert result.complete and result.signed
    assert module.is_installable(result)


def test_report_has_required_android_status_fields(tmp_path, monkeypatch):
    module = load_build_mobile()
    monkeypatch.setattr(module, "RELEASE", tmp_path)
    module.write_report(
        {
            "tests": "PASS",
            "scaffold": "UPDATE PASS",
            "build": "PASS",
            "package": "PASS",
            "apk_type": "DEBUG",
            "signed": "YES",
            "installable": "YES",
            "abi": "arm64-v8a\nx86_64",
            "signature_verification": "PASS",
            "final": "PASS",
        }
    )
    report = (tmp_path / "build_report.txt").read_text()
    for field in (
        "pytest result",
        "Android create/update result",
        "Android build result",
        "Android package result",
        "APK Type: DEBUG",
        "Signed: YES",
        "Installable: YES",
        "INSTALLABLE APK: YES",
        "ABI: arm64-v8a",
        "x86_64",
        "APK path",
        "APK Size",
        "Signature Verification: PASS",
        "SHA256",
        "FINAL STATUS: PASS",
    ):
        assert field in report
