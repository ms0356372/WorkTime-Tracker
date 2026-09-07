import {db} from '../db/database'
import type {DeductionPriority,ISODate,LeaveCycle} from '../models/domain'
import {DexieHolidayRepository,DexieLedgerRepository,DexieSettingsRepository,DexieSpecialDateRepository,DexieWorkRecordRepository} from '../repositories/dexieRepositories'
import {CalendarService} from './calendarService'
import {LedgerService,todayLocal} from './ledgerService'
import {getCurrentLeaveCycle,parseSettlement} from './leaveYearService'

const holidayRepository=new DexieHolidayRepository(db),ledgerRepository=new DexieLedgerRepository(db),recordsRepository=new DexieWorkRecordRepository(db),settingsRepository=new DexieSettingsRepository(db),specialDateRepository=new DexieSpecialDateRepository(db)
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
  const cycles=await db.leaveCycles.orderBy('startDate').toArray(),legacyAnnualOpening=cycle.startDate<activation?entitlement:0
  return ledgerService.rebuild({records,calendar,dailyStandardMinutes:Number.isInteger(standard)&&standard>0?standard:480,trackingStartDate:start,today,priority,annualCycles:cycles,activationDate:activation,legacyAnnualOpening},emit)
}
export async function currentLeaveSummary(today:ISODate=todayLocal()){
  const balances=await ledgerService.currentBalances(),entitlement=Number(await settingsRepository.get('annual_leave_total_minutes','0')),configured=await settingsRepository.get('annual_leave_settlement_date',`${today.slice(0,4)}-12-31`),settlement=parseSettlement(configured!,today)
  return {...balances,cycle:getCurrentLeaveCycle(today,settlement.month,settlement.day,entitlement)}
}
