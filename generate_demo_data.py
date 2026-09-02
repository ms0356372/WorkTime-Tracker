"""Create three months of varied local test data."""
import sys
from datetime import date,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/"src"))
from worktime_tracker.database import Database,WorkRecordRepository
from worktime_tracker.models import WorkRecord,WorkdayType
def main(path="demo.sqlite3"):
 db=Database(path); repo=WorkRecordRepository(db); start=date.today()-timedelta(days=90)
 for i in range(91):
  day=start+timedelta(days=i)
  if day.weekday()<5 or i%17==0:
   end="22:00" if i%19==0 else "19:30" if i%7==0 else "17:00" if i%11==0 else "18:00"
   repo.save(WorkRecord(day,"09:00",end,workday_type=WorkdayType.NORMAL if day.weekday()<5 else WorkdayType.REST,note="自動測試資料"))
 print(f"已建立 {path}")
if __name__=="__main__": main()
