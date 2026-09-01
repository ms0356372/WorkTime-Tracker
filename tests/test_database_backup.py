from datetime import date
from worktime_tracker.database import Database,WorkRecordRepository
from worktime_tracker.models import WorkRecord
from worktime_tracker.services.backup_service import create_backup,restore_backup
def test_database_and_backup(tmp_path):
 db=Database(tmp_path/"a.db"); repo=WorkRecordRepository(db); repo.save(WorkRecord(date(2026,9,1),"09:00","18:00")); backup=tmp_path/"b.json"; create_backup(db,backup); repo.delete(1); restore_backup(db,backup); assert len(repo.all())==1
