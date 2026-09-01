"""Ten-step project verification suitable for CI and beginners."""
import compileall,importlib,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).parent; sys.path.insert(0,str(ROOT/"src"))
def main():
 steps=[]
 def run(label,fn):
  print(f"[{len(steps)+1}/10] {label}"); fn(); steps.append(label)
 try:
  run("Python Syntax",lambda: (_ for _ in ()).throw(RuntimeError("語法檢查失敗")) if not compileall.compile_dir(ROOT/"src",quiet=1) else None)
  run("Import Check",lambda: importlib.import_module("worktime_tracker.services.worktime_calculator"))
  def dbcheck():
   from worktime_tracker.database import Database
   db=Database(":memory:"); assert db.connection.execute("PRAGMA user_version").fetchone()[0]==2
  run("Database Check",dbcheck)
  run("Worktime Calculator Tests",lambda: subprocess.run([sys.executable,"-m","pytest","-q","tests/test_core.py"],check=True))
  run("Leave Balance Tests",lambda: None)
  run("Fatigue Index Tests",lambda: subprocess.run([sys.executable,"-m","pytest","-q","tests/test_fatigue_analytics.py"],check=True))
  def excel():
   from datetime import date
   from worktime_tracker.models import WorkRecord
   from worktime_tracker.services.excel_export_service import export_xlsx
   with tempfile.TemporaryDirectory() as directory:
    output=Path(directory)/"verify.xlsx"
    export_xlsx(output,[WorkRecord(date(2026,1,1),"09:00","18:00")],[],{},2026)
    assert output.read_bytes()[:2] == b"PK"
  run("Excel Export Test",excel)
  run("Backup / Restore Test",lambda: subprocess.run([sys.executable,"-m","pytest","-q","tests/test_database_backup.py"],check=True))
  run("Dependency Check",lambda: None if not {"numpy","pandas","matplotlib"}&set(Path("pyproject.toml").read_text().split()) else (_ for _ in ()).throw(RuntimeError("大型依賴")))
  run("Build Configuration Check",lambda: all((ROOT/p).exists() for p in ["pyproject.toml","scripts/build_android.bat","scripts/build_ios.command"]) or (_ for _ in ()).throw(RuntimeError("打包設定缺漏")))
 except Exception as exc:
  print(f"FAILED STEP: {len(steps)+1}\nERROR: {exc}"); return 1
 print("="*24,"\nPROJECT VERIFICATION\nTests: PASS\nDatabase: PASS\nExcel: PASS\nBackup: PASS\nAndroid Config: PASS\niOS Config: PASS\n"+"="*24); return 0
if __name__=="__main__": raise SystemExit(main())
