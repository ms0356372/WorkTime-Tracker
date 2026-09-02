from datetime import date,timedelta
import pytest
from worktime_tracker.models import WorkRecord
from worktime_tracker.services.worktime_calculator import calculate_work_minutes,calculate_daily_difference,ValidationError
from worktime_tracker.services.balance_service import LeaveBalanceService
@pytest.mark.parametrize("start,end,expected",[("09:00","18:00",480),("09:00","19:30",570),("09:00","17:00",420),("12:30","18:00",300),("13:30","18:00",270)])
def test_work_minutes(start,end,expected): assert calculate_work_minutes(WorkRecord(date(2026,9,1),start,end))==expected
def test_overtime(): assert calculate_daily_difference(calculate_work_minutes(WorkRecord(date(2026,9,1),"09:00","19:30")),480)==90
def test_shortfall_order(): assert LeaveBalanceService().apply_shortfall(120,30)==(-30,-90)
def test_overnight(): assert calculate_work_minutes(WorkRecord(date(2026,9,1),"22:00","06:00",deduct_break=False,overnight=True))==480
def test_overnight_requires_switch():
 with pytest.raises(ValidationError): calculate_work_minutes(WorkRecord(date(2026,9,1),"22:00","06:00",deduct_break=False))
def test_monthly_cap_settles():
 records=[WorkRecord(date(2026,8,1)+timedelta(days=i%28),"09:00","19:00",standard_minutes=480,id=i+1) for i in range(53)]
 ledger=LeaveBalanceService().recalculate_balances(records,monthly_cap=46*60,cap_rule="月結")
 assert ledger[-1].entry_type=="月結" and ledger[-1].comp_change==-420 and ledger[-1].comp_balance==2760
def test_historical_recalculation():
 rows=[WorkRecord(date(2026,6,1),"09:00","19:00",id=1),WorkRecord(date(2026,7,1),"09:00","17:00",id=2),WorkRecord(date(2026,8,1),"09:00","18:00",id=3)]
 before=LeaveBalanceService().recalculate_balances(rows,annual_opening=600)
 rows[0].clock_out="18:00"; after=LeaveBalanceService().recalculate_balances(rows,annual_opening=600)
 assert before[-1].comp_balance==0 and before[-1].annual_balance==600
 assert after[-1].comp_balance==0 and after[-1].annual_balance==540
