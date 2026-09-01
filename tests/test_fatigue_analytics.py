from datetime import date,timedelta
from worktime_tracker.models import WorkRecord
from worktime_tracker.services.fatigue_service import calculate_fatigue_score
from worktime_tracker.services.analytics_service import calculate_month_summary
def test_fatigue_bounded_and_explained():
 rows=[WorkRecord(date(2026,8,1)+timedelta(days=i),"08:00","22:00",deduct_break=False) for i in range(7)]
 result=calculate_fatigue_score(rows); assert 0<=result.score<=100 and result.level in {"低","中度","偏高","高"} and result.reasons
def test_month_summary():
 rows=[WorkRecord(date(2026,8,1),"09:00","18:00")]; s=calculate_month_summary(rows,2026,8); assert s.work_minutes==480 and s.difference==0
