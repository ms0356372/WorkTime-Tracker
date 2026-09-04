from datetime import date, datetime
import sqlite3
import pytest
from worktime_tracker.database import Database, LedgerRepository, SettingsRepository
from worktime_tracker.models import (DeductionPriority, LedgerOrigin, LeaveType,
                                     TransactionType, WorkRecord)
from worktime_tracker.services.balance_service import LeaveBalanceService
from worktime_tracker.services.leave_conversion_service import LeaveConversionService
from worktime_tracker.services.worktime_calculator import ValidationError

def test_comp_to_annual():
 e=LeaveConversionService().convert_leave(LeaveType.COMP_TIME,LeaveType.ANNUAL_LEAVE,120,600,1000)
 assert (e.comp_balance,e.annual_balance)==(480,1120)
def test_annual_to_comp():
 e=LeaveConversionService().convert_leave(LeaveType.ANNUAL_LEAVE,LeaveType.COMP_TIME,180,300,600)
 assert (e.comp_balance,e.annual_balance)==(480,420)
def test_insufficient_is_atomic():
 balances=(60,1000)
 with pytest.raises(ValidationError): LeaveConversionService().convert_leave(LeaveType.COMP_TIME,LeaveType.ANNUAL_LEAVE,120,*balances)
 assert balances==(60,1000)
def test_zero_rejected():
 with pytest.raises(ValidationError): LeaveConversionService().convert_leave(LeaveType.COMP_TIME,LeaveType.ANNUAL_LEAVE,0,60,60)
def test_conversion_ledger_fields():
 e=LeaveConversionService().convert_leave(LeaveType.COMP_TIME,LeaveType.ANNUAL_LEAVE,120,600,1000)
 assert (e.comp_time_change,e.annual_leave_change,e.transaction_type,e.ledger_origin)==(-120,120,TransactionType.LEAVE_CONVERSION,LedgerOrigin.MANUAL)
def test_reversal_roundtrip(tmp_path):
 db=Database(tmp_path/"db.sqlite3"); repo=LedgerRepository(db); service=LeaveConversionService()
 opening=service.convert_leave(LeaveType.ANNUAL_LEAVE,LeaveType.COMP_TIME,300,0,1000,transaction_datetime=datetime(2026,1,1,9)); repo.add(opening)
 original=repo.save_conversion(service,LeaveType.COMP_TIME,LeaveType.ANNUAL_LEAVE,120,when=datetime(2026,1,2,9))
 reversal=repo.save_reversal(service,original,when=datetime(2026,1,3,9))
 assert repo.current_balances()==(300,700) and reversal.transaction_type==TransactionType.REVERSAL
 assert len(repo.all())==3 and repo.all()[-1].reversal_of_id==original.id
def test_manual_survives_historical_recalculation():
 service=LeaveConversionService(); manual=service.convert_leave(LeaveType.COMP_TIME,LeaveType.ANNUAL_LEAVE,240,300,1000,transaction_datetime=datetime(2026,7,1,19))
 manual.id=7
 records=[WorkRecord(date(2026,6,1),"09:00","23:00",id=1),WorkRecord(date(2026,8,1),"09:00","18:00",id=2)]
 records[0].clock_out="22:00"
 ledger=LeaveBalanceService().recalculate_from_date(records,date(2026,5,1),annual_opening=1000,manual_transactions=[manual])
 kept=[e for e in ledger if e.ledger_origin==LedgerOrigin.MANUAL]
 assert len(kept)==1 and kept[0].id==7 and kept[0].annual_balance==1240
def test_comp_first():
 changes=LeaveBalanceService().deduct_leave(120,60,300,DeductionPriority.COMP_TIME_FIRST)
 assert changes==(-60,-60)
def test_annual_first():
 changes=LeaveBalanceService().deduct_leave(120,60,300,DeductionPriority.ANNUAL_LEAVE_FIRST)
 assert changes==(0,-120)
def test_default_priority_persisted(tmp_path):
 db=Database(tmp_path/"db.sqlite3"); assert SettingsRepository(db).deduction_priority()==DeductionPriority.ANNUAL_LEAVE_FIRST
def test_v1_migration_preserves_rows(tmp_path):
 path=tmp_path/"old.sqlite3"; con=sqlite3.connect(path)
 con.executescript("CREATE TABLE work_records(id INTEGER PRIMARY KEY, work_date TEXT NOT NULL UNIQUE, clock_in TEXT, clock_out TEXT, break_start TEXT, break_end TEXT, deduct_break INTEGER NOT NULL DEFAULT 1, standard_minutes INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '', workday_type TEXT NOT NULL, overnight INTEGER NOT NULL DEFAULT 0); CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL,effective_date TEXT); CREATE TABLE leave_cycles(id INTEGER PRIMARY KEY,start_date TEXT,end_date TEXT,total_minutes INTEGER); CREATE TABLE balance_ledger(id INTEGER PRIMARY KEY,entry_date TEXT,entry_type TEXT,reason TEXT,comp_change INTEGER,annual_change INTEGER,comp_balance INTEGER,annual_balance INTEGER,source_record_id INTEGER); CREATE TABLE monthly_settlements(id INTEGER PRIMARY KEY,year INTEGER,month INTEGER,minutes INTEGER,rule TEXT); CREATE TABLE app_metadata(key TEXT PRIMARY KEY,value TEXT); INSERT INTO balance_ledger(entry_date,entry_type,reason,comp_change,annual_change,comp_balance,annual_balance) VALUES('2026-01-01','正常工作','舊資料',60,0,60,0); PRAGMA user_version=1;")
 con.close(); db=Database(path)
 assert db.connection.execute("PRAGMA user_version").fetchone()[0]==5
 assert tuple(db.connection.execute("SELECT reason,ledger_origin FROM balance_ledger").fetchone())==("舊資料","SYSTEM")
