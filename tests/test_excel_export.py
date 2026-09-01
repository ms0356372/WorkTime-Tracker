from datetime import date
from zipfile import ZipFile
from worktime_tracker.models import WorkRecord
from worktime_tracker.services.balance_service import LeaveBalanceService
from worktime_tracker.services.excel_export_service import export_xlsx
def test_excel_export_is_real_xlsx(tmp_path):
 records=[WorkRecord(date(2026,9,1),"09:00","18:00",id=1)]
 ledger=LeaveBalanceService().recalculate_balances(records)
 path=tmp_path/"report.xlsx"; export_xlsx(path,records,ledger,{"扣除順序":"補休優先"},2026)
 with ZipFile(path) as archive:
  assert "xl/worksheets/sheet1.xml" in archive.namelist()
  workbook=archive.read("xl/workbook.xml").decode()
  assert all(name in workbook for name in ["每日工時","月統計","年度統計","假別流水帳","設定"])
