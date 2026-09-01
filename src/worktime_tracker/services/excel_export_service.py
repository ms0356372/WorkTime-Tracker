"""Formatted XLSX exports (XlsxWriter is runtime-light and pure Python)."""
from pathlib import Path
from .analytics_service import calculate_month_summary, calculate_year_summary
from .worktime_calculator import calculate_work_minutes
def export_xlsx(path,records,ledger,settings,year,month=None):
    try:
        import xlsxwriter
    except ModuleNotFoundError:
        from worktime_tracker.utils import minimal_xlsxwriter as xlsxwriter
    wb=xlsxwriter.Workbook(str(Path(path))); head=wb.add_format({"bold":True,"bg_color":"#D9EAF7"})
    duration=wb.add_format({"num_format":"[h]:mm;-[h]:mm"})
    def sheet(name,headers):
        ws=wb.add_worksheet(name); ws.freeze_panes(1,0); ws.autofilter(0,0,0,len(headers)-1); ws.write_row(0,0,headers,head); ws.set_column(0,len(headers)-1,15); return ws
    ws=sheet("每日工時",["日期","星期","工作日類型","上班時間","下班時間","午休開始","午休結束","原始工時","扣除休息","實際工時","基準工時","工時差額","補休增加","補休使用","特休使用","補休餘額","特休餘額","疲累指數","備註"])
    selected=[r for r in records if r.work_date.year==year and (month is None or r.work_date.month==month)]
    for i,r in enumerate(selected,1):
        actual=calculate_work_minutes(r); diff=actual-r.standard_minutes
        ws.write_row(i,0,[r.work_date.isoformat(),r.work_date.strftime("%A"),str(r.workday_type),r.clock_in,r.clock_out,r.break_start,r.break_end,"", "",actual/1440,r.standard_minutes/1440,diff/1440,max(diff,0)/1440,min(diff,0)/1440,"","","","",r.note]); ws.set_row(i,None,duration)
    monthly=sheet("月統計",["月份","工作天數","總工作時數","標準工時","工時差","平均每日工時"])
    for m in range(1,13):
        s=calculate_month_summary(records,year,m); monthly.write_row(m,0,[f"{year}-{m:02}",s.workdays,s.work_minutes/1440,s.standard_minutes/1440,s.difference/1440,s.average_minutes/1440])
    annual=sheet("年度統計",["年度","工作天數","總工作時數","標準工時","年度差額","平均每日工時","最長工作日"]); s=calculate_year_summary(records,year); annual.write_row(1,0,[year,s.workdays,s.work_minutes/1440,s.standard_minutes/1440,s.difference/1440,s.average_minutes/1440,s.longest_date or ""])
    led=sheet("假別流水帳",["日期時間","交易類型","來源假別","目的假別","轉換時數","補休異動","特休異動","補休餘額","特休餘額","備註","來源紀錄 ID"])
    for i,e in enumerate(ledger,1):
        led.write_row(i,0,[e.transaction_datetime.isoformat(sep=" ", timespec="minutes"),str(e.transaction_type),str(e.source_leave_type or ""),str(e.target_leave_type or ""),(e.source_minutes or 0)/1440,e.comp_change/1440,e.annual_change/1440,e.comp_balance/1440,e.annual_balance/1440,e.note or e.reason,e.source_record_id])
    cfg=sheet("設定",["項目","值"])
    for i,(k,v) in enumerate(settings.items(),1): cfg.write_row(i,0,[k,str(v)])
    wb.close()
