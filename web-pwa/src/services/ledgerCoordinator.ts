import {db} from '../db/database'
import type {CompSettlementPolicy,DeductionPriority,ISODate,LeaveCycle} from '../models/domain'
import {DexieCompCycleRepository,DexieCompMonthlySettlementRepository,DexieCompPolicyRepository,DexieHolidayRepository,DexieLedgerRepository,DexieSettingsRepository,DexieSpecialDateRepository,DexieWorkRecordRepository} from '../repositories/dexieRepositories'
import {CalendarService} from './calendarService'
import {LedgerService,todayLocal} from './ledgerService'
import {getCurrentLeaveCycle,parseSettlement} from './leaveYearService'

const holidayRepository=new DexieHolidayRepository(db),ledgerRepository=new DexieLedgerRepository(db),recordsRepository=new DexieWorkRecordRepository(db),settingsRepository=new DexieSettingsRepository(db),specialDateRepository=new DexieSpecialDateRepository(db)
const compPolicyRepository=new DexieCompPolicyRepository(db),compCycleRepository=new DexieCompCycleRepository(db),compSettlementRepository=new DexieCompMonthlySettlementRepository(db)
export const ledgerService=new LedgerService(ledgerRepository)
export async function rebuildLedger(today:ISODate=todayLocal(),emit=true){
  const [records,overrides]=await Promise.all([recordsRepository.all(),specialDateRepository.all()])
  const start=(await settingsRepository.get('work_tracking_start_date')) as ISODate|undefined??today
  const years=new Set<number>([Number(today.slice(0,4))]);for(let y=Number(start.slice(0,4));y<=Number(today.slice(0,4));y++)years.add(y);records.forEach(r=>years.add(Number(r.workDate.slice(0,4))))
  const holidays=(await Promise.all([...years].map(y=>holidayRepository.forYear(y)))).flat(),calendar=new CalendarService(overrides,holidays)
  const standard=Number(await settingsRepository.get('daily_standard_minutes','480')),priority=(await settingsRepository.get('leave_deduction_priority','ANNUAL_LEAVE_FIRST')) as DeductionPriority
  const entitlement=Number(await settingsRepository.get('annual_leave_total_minutes','0')),configured=await settingsRepository.get('annual_leave_settlement_date',`${today.slice(0,4)}-12-31`),settlement=parseSettlement(configured!,today)
  const cycle=getCurrentLeaveCycle(today,settlement.month,settlement.day,entitlement) as LeaveCycle
  const existingCycle=await db.leaveCycles.where('[startDate+endDate]').equals([cycle.startDate,cycle.endDate]).first();await db.leaveCycles.put(existingCycle?{...cycle,id:existingCycle.id}:cycle)
  let activation=(await db.appMetadata.get('settlement_engine_activation_date'))?.value as ISODate|undefined
  if(!activation){activation=today;await db.appMetadata.put({key:'settlement_engine_activation_date',value:activation})}
  const compConfigured=await settingsRepository.get('comp_leave_settlement_date',configured),compDate=parseSettlement(compConfigured!,today),compCycle=getCurrentLeaveCycle(today,compDate.month,compDate.day) as LeaveCycle
  await compCycleRepository.upsert(compCycle)
  let policies=await compPolicyRepository.history();if(!policies.length){const mode=(await settingsRepository.get('comp_settlement_mode','ANNUAL')) as 'ANNUAL'|'MONTHLY',cap=Number(await settingsRepository.get('comp_monthly_cap_minutes','2400')),rate=Number(await settingsRepository.get('comp_cash_hourly_rate_cents','25000'));await compPolicyRepository.save({effectiveFrom:compCycle.startDate,mode,monthlyCapMinutes:cap,cashHourlyRateCents:rate,createdAt:new Date().toISOString()});policies=await compPolicyRepository.history()}
  const cycles=await db.leaveCycles.orderBy('startDate').toArray(),compCycles=await compCycleRepository.all(),legacyAnnualOpening=cycle.startDate<activation?entitlement:0
  return ledgerService.rebuild({records,calendar,dailyStandardMinutes:Number.isInteger(standard)&&standard>0?standard:480,trackingStartDate:start,today,priority,annualCycles:cycles,compCycles,compPolicies:policies,currentCompCycleStart:compCycle.startDate,activationDate:activation,legacyAnnualOpening},emit)
}
export async function currentLeaveSummary(today:ISODate=todayLocal()){
  const balances=await ledgerService.currentBalances(),entitlement=Number(await settingsRepository.get('annual_leave_total_minutes','0')),configured=await settingsRepository.get('annual_leave_settlement_date',`${today.slice(0,4)}-12-31`),settlement=parseSettlement(configured!,today)
  const configuredComp=await settingsRepository.get('comp_leave_settlement_date',configured),compDate=parseSettlement(configuredComp!,today),compCycle=getCurrentLeaveCycle(today,compDate.month,compDate.day),policy=await compPolicyRepository.policyOn(today),compBalances=await ledgerService.currentCompBalances()
  return {...balances,...compBalances,mode:policy?.mode??'ANNUAL',cycle:getCurrentLeaveCycle(today,settlement.month,settlement.day,entitlement),compCycle}
}
export async function saveCompSettings(values:{mode:'ANNUAL'|'MONTHLY';settlementDate:ISODate;monthlyCapMinutes:number;cashHourlyRateCents:number},today:ISODate=todayLocal()){
  if(values.mode==='MONTHLY'&&(values.monthlyCapMinutes<=0||values.cashHourlyRateCents<=0))throw new Error('INVALID_MONTHLY_POLICY')
  const parsed=parseSettlement(values.settlementDate,today),cycle=getCurrentLeaveCycle(today,parsed.month,parsed.day),policy:CompSettlementPolicy={effectiveFrom:cycle.startDate,mode:values.mode,monthlyCapMinutes:values.monthlyCapMinutes,cashHourlyRateCents:values.cashHourlyRateCents,createdAt:new Date().toISOString()}
  const settingKeys=['comp_settlement_mode','comp_leave_settlement_date','comp_monthly_cap_minutes','comp_cash_hourly_rate_cents'],previousSettings=await db.settings.bulkGet(settingKeys),previousPolicies=await db.compPolicies.toArray(),previousCycles=await db.compLeaveCycles.toArray()
  await db.transaction('rw',db.settings,db.compPolicies,db.compLeaveCycles,async()=>{await settingsRepository.set({key:'comp_settlement_mode',value:values.mode});await settingsRepository.set({key:'comp_leave_settlement_date',value:values.settlementDate});await settingsRepository.set({key:'comp_monthly_cap_minutes',value:String(values.monthlyCapMinutes)});await settingsRepository.set({key:'comp_cash_hourly_rate_cents',value:String(values.cashHourlyRateCents)});await compCycleRepository.upsert(cycle);await compPolicyRepository.save(policy)})
  try{await rebuildLedger(today);return {cycle,policy}}catch(error){await db.transaction('rw',db.settings,db.compPolicies,db.compLeaveCycles,async()=>{await db.settings.bulkDelete(settingKeys);const settings=previousSettings.filter(value=>value!==undefined);if(settings.length)await db.settings.bulkPut(settings);await db.compPolicies.clear();if(previousPolicies.length)await db.compPolicies.bulkPut(previousPolicies);await db.compLeaveCycles.clear();if(previousCycles.length)await db.compLeaveCycles.bulkPut(previousCycles)});throw error}
}
export const compSettlementHistory=()=>compSettlementRepository.all()
export const compSettlementForMonth=(year:number,month:number)=>compSettlementRepository.forMonth(year,month)
