from pathlib import Path
import importlib.util

def load_build_mobile():
    spec=importlib.util.spec_from_file_location("build_mobile",Path(__file__).parents[1]/"build_mobile.py")
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

def test_batch_sources_are_ascii_crlf_and_clean():
    from scripts.check_batch_files import validate_batch_file
    root=Path(__file__).parents[1]
    files=[*root.rglob("*.bat"),*root.rglob("*.cmd")]
    assert files and all(not validate_batch_file(path) for path in files)

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
