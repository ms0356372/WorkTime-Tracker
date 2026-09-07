import {describe,expect,it} from 'vitest'
import {CalendarService} from '../services/calendarService'
import {calculateDailyCompEarning,cashAmountCents,replayLedgerWithSettlements} from '../services/ledgerService'
import type {CompSettlementPolicy,ISODate,WorkRecord} from '../models/domain'

describe('daily comp earning cap',()=>{
 const cases=[
  [840,480,false,720,360,0,0],
  [600,480,true,720,120,0,0],
  [720,480,true,720,240,0,0],
  [780,480,true,720,240,0,60],
  [930,480,true,720,240,0,210],
  [420,480,true,720,0,60,0],
  [840,0,true,720,720,0,120],
 ] as const
 it.each(cases)('actual %i standard %i enabled %s cap %i',(actual,standard,enabled,cap,comp,shortfall,excess)=>expect(calculateDailyCompEarning(actual,standard,enabled,cap)).toEqual({compEarnMinutes:comp,shortfallMinutes:shortfall,excessSettlementMinutes:excess}))
 it('uses integer-cent rounding',()=>expect(cashAmountCents(125,25000)).toBe(52083))
 it('accrues independently and settles at 23:59:30 before comp settlement',()=>{
  const policy:CompSettlementPolicy={effectiveFrom:'2025-01-01',mode:'ANNUAL',monthlyCapMinutes:2400,cashHourlyRateCents:25000,dailyCapEnabled:true,dailyCapMinutes:720,createdAt:'2025-01-01T00:00:00Z'}
  const record=(id:number,date:ISODate,out:string):WorkRecord=>({id,workDate:date,clockIn:'00:00',clockOut:out,deductBreak:false,standardMinutes:480,note:'',workdayType:'正常工作日',overnight:false})
  const result=replayLedgerWithSettlements({records:[record(1,'2025-06-02','14:00'),record(2,'2025-06-03','13:00')],calendar:new CalendarService([],[]),dailyStandardMinutes:480,trackingStartDate:'2025-06-02',today:'2026-01-01',priority:'COMP_TIME_FIRST',annualCycles:[],compCycles:[{startDate:'2025-01-01',endDate:'2025-12-31'}],compPolicies:[policy],currentCompCycleStart:'2026-01-01',activationDate:'2025-01-01'})
  expect(result.entries.filter(e=>e.transactionType==='WORKTIME_EARN').map(e=>e.compChange)).toEqual([240,240])
  const accrual=result.entries.filter(e=>e.transactionType==='COMP_DAILY_EXCESS_ACCRUAL');expect(accrual.map(e=>e.sourceMinutes)).toEqual([120,60]);expect(accrual.every(e=>e.compChange===0&&e.annualChange===0&&e.ledgerOrigin==='SYSTEM')).toBe(true)
  const ending=result.entries.filter(e=>e.entryDate==='2025-12-31').map(e=>e.transactionType);expect(ending.slice(-2)).toEqual(['COMP_ANNUAL_EXCESS_CASH_SETTLEMENT','COMP_LEAVE_SETTLEMENT'])
  expect(result.entries.find(e=>e.transactionType==='COMP_ANNUAL_EXCESS_CASH_SETTLEMENT')).toMatchObject({sourceMinutes:180,cashAmountCents:75000,transactionDatetime:'2025-12-31T23:59:30',compChange:0})
 })
})
