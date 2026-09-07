import type {DeductionPriority,ISODate,LedgerEntry,LeaveCycle,WorkRecord} from '../models/domain'
import type {LedgerRepository} from '../repositories/contracts'
import {calculateWorkMinutes} from './workTimeService'
import {CalendarService,localISODate} from './calendarService'

export const LEDGER_CHANGED='ledger-changed'
export const ledgerEvents=new EventTarget()
export interface ReplayInput{records:WorkRecord[];manualEntries?:LedgerEntry[];calendar:CalendarService;dailyStandardMinutes:number;trackingStartDate:ISODate;today:ISODate;priority:DeductionPriority;annualCycles:LeaveCycle[];activationDate:ISODate;legacyAnnualOpening?:number}
const stamp=(date:string,time:string)=>`${date}T${time}`
const created='1970-01-01T00:00:00.000Z'
const base=(entry:Partial<LedgerEntry>&Pick<LedgerEntry,'entryDate'|'entryType'|'reason'|'transactionDatetime'|'transactionType'|'ledgerOrigin'>):LedgerEntry=>({compChange:0,annualChange:0,compBalance:0,annualBalance:0,note:'',createdAt:created,monthlyCompBalance:0,annualCompBalance:0,cashAmountCents:0,cashHourlyRateCents:0,...entry})
const rank:Record<string,number>={ANNUAL_LEAVE_GRANT:0,ADJUSTMENT:1,WORKTIME_EARN:2,WORKTIME_DEDUCTION:2,MISSING_WORKDAY_DEDUCTION:2,ANNUAL_LEAVE_SETTLEMENT:9}
export function deductLeave(shortfall:number,comp:number,annual:number,priority:DeductionPriority):[number,number]{
  let remaining=Math.max(0,shortfall),compChange=0,annualChange=0
  const useComp=()=>{const used=Math.min(Math.max(comp,0),remaining);compChange-=used;remaining-=used}
  const useAnnual=()=>{const used=Math.min(Math.max(annual,0),remaining);annualChange-=used;remaining-=used}
  if(priority==='COMP_TIME_FIRST'){useComp();useAnnual();if(remaining)annualChange-=remaining}else{useAnnual();useComp();if(remaining)compChange-=remaining}
  return [compChange,annualChange]
}
function dates(start:ISODate,end:ISODate):ISODate[]{const out:ISODate[]=[];let [y,m,d]=start.split('-').map(Number),cursor=new Date(Date.UTC(y,m-1,d)),stop=new Date(`${end}T00:00:00Z`);while(cursor<=stop){out.push(`${cursor.getUTCFullYear()}-${String(cursor.getUTCMonth()+1).padStart(2,'0')}-${String(cursor.getUTCDate()).padStart(2,'0')}` as ISODate);cursor.setUTCDate(cursor.getUTCDate()+1)}return out}
export function replayLedger(input:ReplayInput):LedgerEntry[]{
  const events:LedgerEntry[]=(input.manualEntries??[]).filter(e=>e.ledgerOrigin==='MANUAL').map(e=>({...e}))
  if(input.legacyAnnualOpening)events.push(base({entryDate:input.annualCycles[0]?.startDate??input.activationDate,entryType:'年度期初',reason:'年度假別設定',annualChange:input.legacyAnnualOpening,transactionDatetime:stamp(input.annualCycles[0]?.startDate??input.activationDate,'00:00:00'),transactionType:'ADJUSTMENT',ledgerOrigin:'SYSTEM'}))
  for(const cycle of input.annualCycles){if(input.activationDate<=cycle.startDate&&cycle.startDate<=input.today)events.push(base({entryDate:cycle.startDate,entryType:'特休年度核給',reason:`${cycle.startDate.replaceAll('-','/')}～${cycle.endDate.replaceAll('-','/')}`,annualChange:cycle.totalMinutes??0,transactionDatetime:stamp(cycle.startDate,'00:00:00'),transactionType:'ANNUAL_LEAVE_GRANT',ledgerOrigin:'SYSTEM'}));if(input.activationDate<=cycle.endDate&&cycle.endDate<input.today)events.push(base({entryDate:cycle.endDate,entryType:'特休年度結算',reason:`結算 ${cycle.startDate.replaceAll('-','/')}～${cycle.endDate.replaceAll('-','/')}`,transactionDatetime:stamp(cycle.endDate,'23:59:59'),transactionType:'ANNUAL_LEAVE_SETTLEMENT',ledgerOrigin:'SYSTEM'}))}
  const records=new Map(input.records.map(r=>[r.workDate,r]));for(const record of input.records){if(record.workDate>input.today)continue;const actual=calculateWorkMinutes(record),standard=input.calendar.standardMinutesFor(record.workDate,input.dailyStandardMinutes),difference=actual-standard;events.push(base({entryDate:record.workDate,entryType:standard===0&&actual>0?'假日工作':difference>=0?'正常工作':'工時不足',reason:standard===0&&actual>0?input.calendar.getWorkdayReason(record.workDate).label:'依每日工時重新計算',compChange:difference>=0?difference:0,sourceRecordId:record.id,transactionDatetime:stamp(record.workDate,'18:00:00'),transactionType:difference>=0?'WORKTIME_EARN':'WORKTIME_DEDUCTION',ledgerOrigin:'SYSTEM'}))}
  if(input.trackingStartDate<input.today)for(const day of dates(input.trackingStartDate,input.today)){if(day>=input.today)break;if(!records.has(day)&&input.calendar.isWorkday(day))events.push(base({entryDate:day,entryType:'未登錄工作日',reason:'正常上班日無工時紀錄',transactionDatetime:stamp(day,'18:00:00'),transactionType:'MISSING_WORKDAY_DEDUCTION',ledgerOrigin:'SYSTEM'}))}
  events.sort((a,b)=>a.transactionDatetime.localeCompare(b.transactionDatetime)||(rank[a.transactionType]??5)-(rank[b.transactionType]??5)||(a.id??0)-(b.id??0))
  let comp=0,annual=0;return events.map(event=>{let compChange=event.compChange,annualChange=event.annualChange;if(event.transactionType==='ANNUAL_LEAVE_SETTLEMENT')annualChange=-annual;else if(event.transactionType==='WORKTIME_DEDUCTION'||event.transactionType==='MISSING_WORKDAY_DEDUCTION'){const record=records.get(event.entryDate),standard=input.calendar.standardMinutesFor(event.entryDate,input.dailyStandardMinutes),shortfall=record?standard-calculateWorkMinutes(record):standard;[compChange,annualChange]=deductLeave(shortfall,comp,annual,input.priority)}comp+=compChange;annual+=annualChange;return {...event,compChange,annualChange,compBalance:comp,annualBalance:annual,monthlyCompBalance:0,annualCompBalance:comp}})
}
export class LedgerService{constructor(private repository:LedgerRepository){}async rebuild(input:Omit<ReplayInput,'manualEntries'>,emit=true){const manual=await this.repository.getManual(),entries=replayLedger({...input,manualEntries:manual});await this.repository.replaceSystem(entries);if(emit)ledgerEvents.dispatchEvent(new Event(LEDGER_CHANGED));return entries}currentBalances(){return this.repository.currentBalances()}}
export function todayLocal():ISODate{return localISODate() as ISODate}
