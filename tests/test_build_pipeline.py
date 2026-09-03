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


def test_briefcase_debug_apk_skips_gradle_fallback(tmp_path, monkeypatch):
    module = load_build_mobile()
    monkeypatch.setattr(module, "BUILD", tmp_path)
    apk = (
        tmp_path
        / "worktime_tracker"
        / "android"
        / "gradle"
        / "app"
        / "build"
        / "outputs"
        / "apk"
        / "debug"
        / "app-debug.apk"
    )
    apk.parent.mkdir(parents=True)
    apk.write_bytes(b"apk")
    monkeypatch.setattr(
        module,
        "run_gradle_debug",
        lambda: (_ for _ in ()).throw(AssertionError("Gradle must not run")),
    )
    assert module.obtain_debug_apk() == apk


def test_gradle_is_only_fallback_when_briefcase_apk_is_absent(tmp_path, monkeypatch):
    module = load_build_mobile()
    monkeypatch.setattr(module, "BUILD", tmp_path)
    apk = (
        tmp_path
        / "gradle"
        / "app"
        / "build"
        / "outputs"
        / "apk"
        / "debug"
        / "app-debug.apk"
    )

    def create_fallback_apk():
        apk.parent.mkdir(parents=True)
        apk.write_bytes(b"apk")

    monkeypatch.setattr(module, "run_gradle_debug", create_fallback_apk)
    assert module.obtain_debug_apk() == apk


def test_gradle_fallback_checks_java_before_running(monkeypatch):
    module = load_build_mobile()
    monkeypatch.delenv("JAVA_HOME", raising=False)
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    try:
        module.run_gradle_debug()
    except RuntimeError as exc:
        assert "JAVA_HOME" in str(exc)
    else:
        raise AssertionError("Gradle fallback must reject a missing Java runtime")


def test_debug_build_artifact_naming():
    module = load_build_mobile()
    assert module.artifact_name("debug") == "工時管家-0.7.0-debug.apk"
    assert module.artifact_name("release") == "工時管家-0.7.0-release-unsigned.apk"
    assert module.artifact_name("release", signed=True) == "工時管家-0.7.0-release.apk"


def test_option_container_material_dependency_is_persistent():
    import tomllib

    root = Path(__file__).parents[1]
    app_source = (root / "src/worktime_tracker/app.py").read_text(encoding="utf-8")
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    android = config["tool"]["briefcase"]["app"]["worktime_tracker"]["android"]
    assert "toga.OptionContainer" in app_source
    assert "toga-android>=0.5,<0.6" in android["requires"]
    assert (
        "com.google.android.material:material:1.12.0"
        in android["build_gradle_dependencies"]
    )


def test_generated_gradle_contains_material_dependency(tmp_path, monkeypatch):
    module = load_build_mobile()
    monkeypatch.setattr(module, "BUILD", tmp_path)
    gradle = (
        tmp_path / "worktime_tracker" / "android" / "gradle" / "app" / "build.gradle"
    )
    gradle.parent.mkdir(parents=True)
    gradle.write_text(
        "dependencies {\n"
        "    implementation 'com.google.android.material:material:1.12.0'\n"
        "}\n",
        encoding="utf-8",
    )
    module.validate_generated_gradle_dependencies()


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
    report = (tmp_path / "build_report.txt").read_text(encoding="utf-8")
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
