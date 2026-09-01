"""Cross-platform Briefcase build driver with reports and artifact auditing."""
import hashlib,importlib.metadata,platform,shutil,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from src.worktime_tracker.config import APP_VERSION,BUILD_SIZE_WARNING_MB
ROOT=Path(__file__).parent; RELEASE=ROOT/"release"
def command(args): print("+",*args); subprocess.run(args,cwd=ROOT,check=True)
def artifacts(): return [p for p in (ROOT/"build").rglob("*") if p.suffix.lower() in {".apk",".aab",".ipa"}]
def report(test,build,artifact=None):
 size=artifact.stat().st_size if artifact else 0; sha=hashlib.sha256(artifact.read_bytes()).hexdigest() if artifact else "N/A"
 RELEASE.mkdir(exist_ok=True); (RELEASE/"build_report.txt").write_text(f"APP Version: {APP_VERSION}\nBuild Date: {datetime.now(timezone.utc).isoformat()}\nPython Version: {platform.python_version()}\nBriefcase Version: {version('briefcase')}\nToga Version: {version('toga')}\nPlatform: {platform.platform()}\nTests: {test}\nBuild: {build}\nArtifact: {artifact or 'N/A'}\nFile Size: {size/1048576:.2f} MB\nSHA256: {sha}\n",encoding="utf-8")
 (RELEASE/"dependency_report.txt").write_text("Runtime: toga（GUI，使用中）\nRuntime: XlsxWriter（Excel 輸出，使用中）\nBuild only: briefcase\nDevelopment only: pytest, ruff\n",encoding="utf-8")
 if size/1048576>BUILD_SIZE_WARNING_MB: print("APP 檔案偏大，請檢查是否存在非必要 dependency 或 asset。")
def version(name):
 try:return importlib.metadata.version(name)
 except importlib.metadata.PackageNotFoundError:return "not installed"
def main():
 action=sys.argv[1] if len(sys.argv)>1 else ("all" if platform.system()=="Darwin" else "android")
 if action=="clean": shutil.rmtree(ROOT/"build",ignore_errors=True); return 0
 command([sys.executable,"-m","pytest","-q"])
 if action=="test": report("PASS","SKIPPED"); return 0
 targets=["android"] if action=="android" else ["iOS"] if action=="ios" else ["android","iOS"]
 if "iOS" in targets and platform.system()!="Darwin": print("iOS 需要 macOS + Xcode，已跳過。"); targets.remove("iOS")
 try:
  for target in targets:
   command([sys.executable,"-m","briefcase","create",target]); command([sys.executable,"-m","briefcase","build",target]); command([sys.executable,"-m","briefcase","package",target])
  found=artifacts(); artifact=found[-1] if found else None
  if artifact:
   dest=RELEASE/("android" if artifact.suffix in {".apk",".aab"} else "ios"); dest.mkdir(parents=True,exist_ok=True); artifact=Path(shutil.copy2(artifact,dest/artifact.name))
  report("PASS","PASS",artifact); return 0
 except Exception: report("PASS","FAIL"); raise
if __name__=="__main__": raise SystemExit(main())
