"""Standard-library monthly and yearly aggregations."""
from dataclasses import dataclass
from statistics import mean
from worktime_tracker.models import WorkRecord
from .worktime_calculator import calculate_work_minutes
@dataclass(frozen=True)
class Summary:
    work_minutes:int; standard_minutes:int; difference:int; workdays:int; average_minutes:int; longest_date:str|None; longest_minutes:int
def summarize(records:list[WorkRecord]) -> Summary:
    values=[(r,calculate_work_minutes(r)) for r in records]
    total=sum(v for _,v in values); standard=sum(r.standard_minutes for r,_ in values)
    longest=max(values,key=lambda x:x[1],default=None)
    return Summary(total,standard,total-standard,len(values),round(mean([v for _,v in values])) if values else 0,longest[0].work_date.isoformat() if longest else None,longest[1] if longest else 0)
def calculate_month_summary(records:list[WorkRecord],year:int,month:int)->Summary: return summarize([r for r in records if r.work_date.year==year and r.work_date.month==month])
def calculate_year_summary(records:list[WorkRecord],year:int)->Summary: return summarize([r for r in records if r.work_date.year==year])

def calculate_conversion_summary(entries, year: int) -> dict[str, int]:
    """Conversion totals are distinct from leave usage totals."""
    from worktime_tracker.models import LeaveType, TransactionType
    comp_to_annual = annual_to_comp = 0
    for entry in entries:
        if entry.entry_date.year != year or entry.transaction_type != TransactionType.LEAVE_CONVERSION:
            continue
        if entry.source_leave_type == LeaveType.COMP_TIME: comp_to_annual += entry.source_minutes or 0
        elif entry.source_leave_type == LeaveType.ANNUAL_LEAVE: annual_to_comp += entry.source_minutes or 0
    return {"comp_to_annual_minutes": comp_to_annual, "annual_to_comp_minutes": annual_to_comp}
