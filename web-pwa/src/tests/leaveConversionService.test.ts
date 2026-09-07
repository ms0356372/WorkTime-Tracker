import 'fake-indexeddb/auto'
import {afterEach,describe,expect,it} from 'vitest'
import {WorkTimeDatabase} from '../db/database'
import {DexieLedgerRepository} from '../repositories/dexieRepositories'
import {createConversionReversal,createLeaveConversion} from '../services/leaveConversionService'
import {replayLedger} from '../services/ledgerService'
import {CalendarService} from '../services/calendarService'
import type {LedgerEntry} from '../models/domain'

const when=new Date(2026,8,7,10,30),conversion=(source:'COMP_TIME'|'ANNUAL_LEAVE'='COMP_TIME',minutes=120)=>createLeaveConversion(source,source==='COMP_TIME'?'ANNUAL_LEAVE':'COMP_TIME',minutes,600,1000,'',when)
const replay=(manualEntries:LedgerEntry[],policies:any[]=[])=>replayLedger({records:[],manualEntries,calendar:new CalendarService([],[]),dailyStandardMinutes:480,trackingStartDate:'2026-09-07',today:'2026-09-07',priority:'COMP_TIME_FIRST',annualCycles:[],compPolicies:policies,currentCompCycleStart:'2026-09-01',activationDate:'2026-09-07'})

describe('leave conversion parity',()=>{
  it('converts comp to annual 1:1 in integer minutes',()=>expect(conversion()).toMatchObject({compChange:-120,annualChange:120,sourceMinutes:120,targetMinutes:120,compBalance:0,annualBalance:0}))
  it('converts annual to comp 1:1',()=>expect(conversion('ANNUAL_LEAVE',180)).toMatchObject({compChange:180,annualChange:-180,sourceMinutes:180,targetMinutes:180}))
  it('writes complete MANUAL conversion metadata and local date',()=>expect(conversion()).toMatchObject({entryDate:'2026-09-07',transactionType:'LEAVE_CONVERSION',ledgerOrigin:'MANUAL',sourceLeaveType:'COMP_TIME',targetLeaveType:'ANNUAL_LEAVE'}))
  it('uses the Python fallback note and trims a supplied note',()=>{expect(conversion().note).toBe('補休轉特休 2 小時');expect(createLeaveConversion('COMP_TIME','ANNUAL_LEAVE',90,100,0,'  自訂  ',when).note).toBe('自訂')})
  it.each([[0,'請輸入'],[-1,'請輸入'],[1.5,'請輸入']] as const)('rejects invalid integer amount %s',(amount,message)=>expect(()=>createLeaveConversion('COMP_TIME','ANNUAL_LEAVE',amount,10,10)).toThrow(message))
  it('rejects same types without writing a candidate',()=>expect(()=>createLeaveConversion('COMP_TIME','COMP_TIME',60,60,60)).toThrow('不可相同'))
  it('rejects insufficient and negative source balances',()=>{expect(()=>createLeaveConversion('COMP_TIME','ANNUAL_LEAVE',61,60,100)).toThrow('補休餘額不足');expect(()=>createLeaveConversion('ANNUAL_LEAVE','COMP_TIME',1,100,-1)).toThrow('特休餘額不足')})
  it('creates an exact append-only reversal with swapped metadata',()=>{const original={...conversion(),id:15},row=createConversionReversal(original,480,1120,'',new Date(2026,8,9,15,30));expect(row).toMatchObject({transactionType:'REVERSAL',ledgerOrigin:'MANUAL',compChange:120,annualChange:-120,reversalOfId:15,sourceLeaveType:'ANNUAL_LEAVE',targetLeaveType:'COMP_TIME',sourceMinutes:120,targetMinutes:120,note:'撤銷轉換 #15'})})
  it('rejects unsaved, non-conversion, and reversal rows',()=>{expect(()=>createConversionReversal(conversion(),600,1000)).toThrow('尚未儲存');const adjustment={...conversion(),id:1,transactionType:'ADJUSTMENT' as const};expect(()=>createConversionReversal(adjustment,600,1000)).toThrow('只有假別轉換');const reversal={...adjustment,transactionType:'REVERSAL' as const};expect(()=>createConversionReversal(reversal,600,1000)).toThrow('只有假別轉換')})
  it('validates current comp needed to reverse annual to comp',()=>expect(()=>createConversionReversal({...conversion('ANNUAL_LEAVE'),id:1},119,1000)).toThrow('目前補休餘額不足'))
  it('validates current annual needed to reverse comp to annual',()=>expect(()=>createConversionReversal({...conversion(),id:1},1000,119)).toThrow('目前特休餘額不足'))
  it('roundtrips balances while retaining both audit events',()=>{const original={...conversion(),id:1},reversal={...createConversionReversal(original,480,1120,'',new Date(2026,8,7,11,30)),id:2},entries=replay([original,reversal]);expect(entries).toHaveLength(2);expect(entries.at(-1)).toMatchObject({compBalance:0,annualBalance:0,reversalOfId:1})})
  it('preserves immutable manual identity and payload while recalculating snapshots',()=>{const original={...conversion(),id:7,compBalance:999,annualBalance:999},[row]=replay([original]);expect(row).toMatchObject({id:7,compChange:-120,annualChange:120,transactionDatetime:original.transactionDatetime,note:original.note,compBalance:-120,annualBalance:120})})
  it('routes conversion and reversal deltas through MONTHLY buckets',()=>{const policy={effectiveFrom:'2026-09-01',mode:'MONTHLY' as const,monthlyCapMinutes:2400,cashHourlyRateCents:0,createdAt:'x'},gain={...conversion('ANNUAL_LEAVE'),id:1},loss={...createConversionReversal(gain,120,880,'',new Date(2026,8,7,11,30)),id:2},rows=replay([gain,loss],[policy]);expect(rows.map(r=>[r.monthlyCompBalance,r.annualCompBalance,r.compBalance])).toEqual([[120,0,120],[0,0,0]])})
})

describe('typed audit repository',()=>{let db:WorkTimeDatabase|undefined;afterEach(async()=>{await db?.delete()})
  it('returns newest-first history and enforces MANUAL append',async()=>{db=new WorkTimeDatabase(`phase7-${crypto.randomUUID()}`);const repo=new DexieLedgerRepository(db),one={...conversion(),transactionDatetime:'2026-09-01T10:00:00'},id=await repo.appendManual(one),two={...createConversionReversal({...one,id},600,1000),transactionDatetime:'2026-09-02T10:00:00'};await repo.appendManual(two);expect((await repo.conversionEntries()).map(e=>e.transactionType)).toEqual(['REVERSAL','LEAVE_CONVERSION']);expect(await repo.isReversed(id)).toBe(true);expect((await repo.findReversalFor(id))?.reversalOfId).toBe(id);await expect(repo.appendManual({...one,ledgerOrigin:'SYSTEM'})).rejects.toThrow('ONLY_MANUAL')})
  it('deletes only rollback MANUAL rows and leaves SYSTEM rows untouched',async()=>{db=new WorkTimeDatabase(`phase7-${crypto.randomUUID()}`);const repo=new DexieLedgerRepository(db),manual=await repo.appendManual(conversion()),system=await repo.add({...conversion(),ledgerOrigin:'SYSTEM'});await repo.deleteManual(manual);await repo.deleteManual(system);expect(await repo.getById(manual)).toBeUndefined();expect(await repo.getById(system)).toBeDefined()})
})
