import type {ISODate,LedgerEntry,LeaveType} from '../models/domain'
import type {LedgerRepository} from '../repositories/contracts'
import {ledgerRepository} from '../repositories'
import {LEDGER_CHANGED,ledgerEvents} from './ledgerService'
import {currentLeaveSummary,rebuildLedger} from './ledgerCoordinator'

export class LeaveConversionError extends Error{}
export const leaveLabel=(type:LeaveType)=>type==='COMP_TIME'?'補休':'特休'
export function formatConversionMinutes(minutes:number){const hours=Math.floor(minutes/60),rest=minutes%60;return `${hours} 小時${rest?` ${rest} 分`:''}`}
function localDate(when:Date):ISODate{const y=when.getFullYear(),m=String(when.getMonth()+1).padStart(2,'0'),d=String(when.getDate()).padStart(2,'0');return `${y}-${m}-${d}` as ISODate}
function localDatetime(when:Date){const p=(n:number)=>String(n).padStart(2,'0');return `${localDate(when)}T${p(when.getHours())}:${p(when.getMinutes())}:${p(when.getSeconds())}.${String(when.getMilliseconds()).padStart(3,'0')}`}
const base=(when:Date):Pick<LedgerEntry,'entryDate'|'transactionDatetime'|'createdAt'|'compBalance'|'annualBalance'|'monthlyCompBalance'|'annualCompBalance'|'cashAmountCents'|'cashHourlyRateCents'>=>({entryDate:localDate(when),transactionDatetime:localDatetime(when),createdAt:when.toISOString(),compBalance:0,annualBalance:0,monthlyCompBalance:0,annualCompBalance:0,cashAmountCents:0,cashHourlyRateCents:0})
export function createLeaveConversion(source:LeaveType,target:LeaveType,minutes:number,comp:number,annual:number,note='',when=new Date()):LedgerEntry{
  if(source===target)throw new LeaveConversionError('來源假別與目的假別不可相同。')
  if(!Number.isInteger(minutes)||minutes<=0)throw new LeaveConversionError('請輸入大於 0 的轉換時數。')
  const balance=source==='COMP_TIME'?comp:annual
  if(minutes>balance)throw new LeaveConversionError(`${leaveLabel(source)}餘額不足，目前可轉換時數為 ${formatConversionMinutes(balance)}。`)
  const reason=note.trim()||`${leaveLabel(source)}轉${leaveLabel(target)} ${formatConversionMinutes(minutes)}`
  return {...base(when),entryType:'假別轉換',reason,note:reason,compChange:source==='COMP_TIME'?-minutes:minutes,annualChange:source==='ANNUAL_LEAVE'?-minutes:minutes,transactionType:'LEAVE_CONVERSION',ledgerOrigin:'MANUAL',sourceLeaveType:source,targetLeaveType:target,sourceMinutes:minutes,targetMinutes:minutes}
}
export function createConversionReversal(original:LedgerEntry,comp:number,annual:number,note='',when=new Date()):LedgerEntry{
  if(original.transactionType!=='LEAVE_CONVERSION')throw new LeaveConversionError('只有假別轉換紀錄可以撤銷。')
  if(original.id===undefined)throw new LeaveConversionError('原始轉換尚未儲存，無法撤銷。')
  if(comp<Math.max(original.compChange,0))throw new LeaveConversionError('目前補休餘額不足，無法完整撤銷此筆轉換。')
  if(annual<Math.max(original.annualChange,0))throw new LeaveConversionError('目前特休餘額不足，無法完整撤銷此筆轉換。')
  const reason=note.trim()||`撤銷轉換 #${original.id}`
  return {...base(when),entryType:'撤銷轉換',reason,note:reason,compChange:-original.compChange,annualChange:-original.annualChange,transactionType:'REVERSAL',ledgerOrigin:'MANUAL',sourceLeaveType:original.targetLeaveType,targetLeaveType:original.sourceLeaveType,sourceMinutes:original.targetMinutes,targetMinutes:original.sourceMinutes,reversalOfId:original.id}
}

let mutation:Promise<unknown>=Promise.resolve()
function serialize<T>(operation:()=>Promise<T>):Promise<T>{const next=mutation.then(operation,operation);mutation=next.then(()=>undefined,()=>undefined);return next}
async function appendAndReplay(repository:LedgerRepository,entry:LedgerEntry,today?:ISODate){let id:number;try{id=entry.transactionType==='REVERSAL'?await repository.appendReversal(entry):await repository.appendManual(entry)}catch(error){if(error instanceof Error&&error.message==='ALREADY_REVERSED')throw new LeaveConversionError('此筆轉換已撤銷。');throw error}try{await rebuildLedger(today, false);ledgerEvents.dispatchEvent(new Event(LEDGER_CHANGED));return {...entry,id}}catch{await repository.deleteManual(id);throw new LeaveConversionError('資料重算失敗，原資料仍保留。')}}
export function convertLeave(input:{sourceType:LeaveType;targetType:LeaveType;minutes:number;note?:string;transactionDatetime?:Date;today?:ISODate},repository:LedgerRepository=ledgerRepository){return serialize(async()=>{const balances=await currentLeaveSummary(input.today);return appendAndReplay(repository,createLeaveConversion(input.sourceType,input.targetType,input.minutes,balances.compBalanceMinutes,balances.annualBalanceMinutes,input.note,input.transactionDatetime),input.today)})}
export function reverseLeaveConversion(originalId:number|undefined,note='',transactionDatetime?:Date,today?:ISODate,repository:LedgerRepository=ledgerRepository){return serialize(async()=>{
  if(originalId===undefined)throw new LeaveConversionError('原始轉換尚未儲存，無法撤銷。')
  const original=await repository.getById(originalId);if(!original)throw new LeaveConversionError('找不到原始轉換紀錄。')
  if(original.transactionType!=='LEAVE_CONVERSION')throw new LeaveConversionError('只有假別轉換紀錄可以撤銷。')
  if(await repository.isReversed(originalId))throw new LeaveConversionError('此筆轉換已撤銷。')
  const balances=await currentLeaveSummary(today),entry=createConversionReversal(original,balances.compBalanceMinutes,balances.annualBalanceMinutes,note,transactionDatetime)
  if(await repository.isReversed(originalId))throw new LeaveConversionError('此筆轉換已撤銷。')
  return appendAndReplay(repository,entry,today)
})}
export async function conversionAuditHistory(repository:LedgerRepository=ledgerRepository){const entries=await repository.conversionEntries(),reversed=new Set(entries.filter(e=>e.transactionType==='REVERSAL'&&e.reversalOfId!==undefined).map(e=>e.reversalOfId));return entries.map(entry=>({...entry,status:entry.transactionType==='REVERSAL'?'REVERSAL':reversed.has(entry.id)?'REVERSED':'ACTIVE'} as const))}
