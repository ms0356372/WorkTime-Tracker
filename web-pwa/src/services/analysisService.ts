import type { ISODate, WorkRecord } from '../models/domain'
import { calculateWorkMinutes } from './workTimeService'
import type { CalendarService } from './calendarService'
import { localISODate } from './calendarService'

export interface Summary {workMinutes:number;attendanceDays:number;averageMinutes:number;overtimeMinutes:number;shortfallMinutes:number;holidayWorkMinutes:number;scheduledWorkdays:number;missingWorkdays:number}

export interface AnalysisOptions { year:number; month:number; dailyStandardMinutes:number; calculationStartDate:ISODate; today?:ISODate }
export function monthBounds(year:number, month:number):{start:ISODate;end:ISODate} {
  const pad=(n:number)=>String(n).padStart(2,'0'), last=new Date(year,month,0).getDate()
  return {start:`${year}-${pad(month)}-01` as ISODate,end:`${year}-${pad(month)}-${pad(last)}` as ISODate}
}
function datesBetween(start:string,end:string):ISODate[]{
  const [y,m,d]=start.split('-').map(Number), cursor=new Date(y,m-1,d), result:ISODate[]=[]
  while(localISODate(cursor)<=end){result.push(localISODate(cursor));cursor.setDate(cursor.getDate()+1)}
  return result
}
export function summarizeMonth(records:WorkRecord[], calendar:CalendarService, options:AnalysisOptions):Summary {
  const {start,end}=monthBounds(options.year,options.month), today=options.today ?? localISODate()
  const selected=records.filter((r)=>r.workDate>=start&&r.workDate<=end)
  let workMinutes=0,overtimeMinutes=0,shortfallMinutes=0,holidayWorkMinutes=0,attendanceDays=0
  const recorded=new Set<string>()
  for(const record of selected){
    const actual=calculateWorkMinutes(record); if(actual>0) attendanceDays++; recorded.add(record.workDate); workMinutes+=actual
    const required=calendar.standardMinutesFor(record.workDate,options.dailyStandardMinutes), difference=actual-required
    overtimeMinutes+=Math.max(difference,0);shortfallMinutes+=Math.max(-difference,0)
    if(!calendar.isWorkday(record.workDate))holidayWorkMinutes+=actual
  }
  const analysisStart=start>options.calculationStartDate?start:options.calculationStartDate
  let scheduledWorkdays=0,missingWorkdays=0
  if(analysisStart<=end){for(const date of datesBetween(analysisStart,end)){
    if(!calendar.isWorkday(date))continue
    scheduledWorkdays++
    // Python deliberately skips unsafe missing deductions when no official cache exists.
    if(date<today&&!recorded.has(date)&&(calendar.hasHolidayData(Number(date.slice(0,4)))||calendar.getWorkdayReason(date).source==='SPECIAL_OVERRIDE')){
      missingWorkdays++;shortfallMinutes+=options.dailyStandardMinutes
    }
  }}
  return {workMinutes,attendanceDays,averageMinutes:attendanceDays?Math.round(workMinutes/attendanceDays):0,overtimeMinutes,shortfallMinutes,holidayWorkMinutes,scheduledWorkdays,missingWorkdays}
}

/** Backward-compatible basic helper retained for callers that do not have a calendar. */
export function summarize(records:WorkRecord[]):Omit<Summary,'scheduledWorkdays'|'missingWorkdays'> {let workMinutes=0,overtimeMinutes=0,shortfallMinutes=0,holidayWorkMinutes=0,attendanceDays=0;for(const record of records){const actual=calculateWorkMinutes(record),difference=actual-record.standardMinutes;workMinutes+=actual;if(actual>0)attendanceDays++;overtimeMinutes+=Math.max(difference,0);shortfallMinutes+=Math.max(-difference,0);if(record.workdayType==='假日'||record.workdayType==='休息日')holidayWorkMinutes+=actual}return {workMinutes,attendanceDays,averageMinutes:attendanceDays?Math.round(workMinutes/attendanceDays):0,overtimeMinutes,shortfallMinutes,holidayWorkMinutes}}
