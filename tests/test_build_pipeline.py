from pathlib import Path
import importlib.util

def load_build_mobile():
    spec=importlib.util.spec_from_file_location("build_mobile",Path(__file__).parents[1]/"build_mobile.py")
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

def test_batch_sources_are_ascii_crlf_and_clean():
    from scripts.check_batch_files import iter_batch_files, validate_batch_file
    files=list(iter_batch_files())
    assert files and all(not validate_batch_file(path) for path in files)

def test_batch_source_discovery_ignores_virtual_environments(tmp_path,monkeypatch):
    from scripts import check_batch_files
    monkeypatch.setattr(check_batch_files,"ROOT",tmp_path)
    source=tmp_path/"build.cmd"; source.write_bytes(b"@echo off\r\necho %~dp0\r\n")
    generated=tmp_path/".venv"/"Scripts"/"activate.bat"
    generated.parent.mkdir(parents=True); generated.write_bytes(b"generated\n")
    assert list(check_batch_files.iter_batch_files())==[source]

def test_apk_search_is_recursive(tmp_path,monkeypatch):
    module=load_build_mobile(); monkeypatch.setattr(module,"BUILD",tmp_path)
    apk=tmp_path/"deep"/"outputs"/"app-debug.apk"; apk.parent.mkdir(parents=True); apk.write_bytes(b"apk")
    assert module.find_apks()==[apk]

def test_report_has_required_android_status_fields(tmp_path,monkeypatch):
    module=load_build_mobile(); monkeypatch.setattr(module,"RELEASE",tmp_path)
    module.write_report({"tests":"PASS","scaffold":"UPDATE PASS","build":"PASS","package":"PASS","final":"PASS"})
    report=(tmp_path/"build_report.txt").read_text()
    for field in ("pytest result","Android create/update result","Android build result","Android package result","APK path","APK size","SHA256","FINAL STATUS: PASS"):
        assert field in report
