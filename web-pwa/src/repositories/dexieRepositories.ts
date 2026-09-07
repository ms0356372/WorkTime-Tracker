import type { WorkTimeDatabase } from '../db/database'
import type { CalendarOverride, CompMonthlySettlement, CompSettlementPolicy, LedgerEntry, LeaveCycle, OfficialHoliday, Setting, WorkRecord } from '../models/domain'
import type {
  HolidayRepository,
  CompCycleRepository, CompMonthlySettlementRepository, CompPolicyRepository,
  LedgerRepository,
  SettingsRepository,
  SpecialDateRepository,
  WorkRecordRepository,
} from './contracts'
import { nextMonth } from '../utils/date'
import { normalizeOverride } from '../services/specialDateService'
import { validateHolidayYear } from '../services/holidayService'

export class DexieWorkRecordRepository implements WorkRecordRepository {
  constructor(private database: WorkTimeDatabase) {}

  async save(record: WorkRecord): Promise<number> {
    const found = await this.database.workRecords
      .where('workDate')
      .equals(record.workDate)
      .first()
    const value = found ? { ...record, id: found.id } : record

    return this.database.workRecords.put(value)
  }
  all():Promise<WorkRecord[]>{return this.database.workRecords.orderBy('workDate').toArray()}

  getByDate(date: string): Promise<WorkRecord | undefined> {
    return this.database.workRecords.where('workDate').equals(date).first()
  }

  async recordsForMonth(year: number, month: number): Promise<WorkRecord[]> {
    const end = nextMonth({ year, month })
    const start = `${year}-${String(month).padStart(2, '0')}-01`
    const stop = `${end.year}-${String(end.month).padStart(2, '0')}-01`

    return this.database.workRecords
      .where('workDate')
      .between(start, stop, true, false)
      .reverse()
      .sortBy('workDate')
  }

  recordsForYear(year: number): Promise<WorkRecord[]> {
    return this.database.workRecords.where('workDate').between(`${year}-01-01`, `${year + 1}-01-01`, true, false).toArray()
  }

  async recent(limit = 7): Promise<WorkRecord[]> {
    return this.database.workRecords.orderBy('workDate').reverse().limit(limit).toArray()
  }

  async delete(id: number): Promise<void> {
    await this.database.workRecords.delete(id)
  }
}

export class DexieSettingsRepository implements SettingsRepository {
  constructor(private database: WorkTimeDatabase) {}

  async get(key: string, fallback?: string): Promise<string | undefined> {
    return (await this.database.settings.get(key))?.value ?? fallback
  }

  async set(setting: Setting): Promise<void> {
    await this.database.settings.put(setting)
  }

  async setLunchBreak(start: string, end: string): Promise<void> {
    await this.database.transaction('rw', this.database.settings, async () => {
      await this.set({ key: 'lunch_break_start', value: start })
      await this.set({ key: 'lunch_break_end', value: end })
    })
  }
}

export class DexieLedgerRepository implements LedgerRepository {
  constructor(private database: WorkTimeDatabase) {}

  all(): Promise<LedgerEntry[]> {
    return this.database.ledger.orderBy('transactionDatetime').toArray()
  }

  add(entry: LedgerEntry): Promise<number> {
    return this.database.ledger.add(entry)
  }
  getSystem():Promise<LedgerEntry[]>{return this.database.ledger.where('ledgerOrigin').equals('SYSTEM').sortBy('transactionDatetime')}
  getManual():Promise<LedgerEntry[]>{return this.database.ledger.where('ledgerOrigin').equals('MANUAL').sortBy('transactionDatetime')}
  async replaceSystem(entries:LedgerEntry[]):Promise<void>{
    await this.database.transaction('rw',this.database.ledger,async()=>{
      await this.database.ledger.where('ledgerOrigin').equals('SYSTEM').delete()
      const manual=new Map((await this.database.ledger.where('ledgerOrigin').equals('MANUAL').toArray()).map(x=>[x.id,x]))
      for(const entry of entries){
        if(entry.ledgerOrigin==='MANUAL'&&entry.id&&manual.has(entry.id))await this.database.ledger.update(entry.id,{compBalance:entry.compBalance,annualBalance:entry.annualBalance,monthlyCompBalance:entry.monthlyCompBalance,annualCompBalance:entry.annualCompBalance})
        else if(entry.ledgerOrigin==='SYSTEM')await this.database.ledger.add({...entry,id:undefined})
      }
    })
  }
  async replaceDerived(entries:LedgerEntry[],settlements:CompMonthlySettlement[]):Promise<void>{
    await this.database.transaction('rw',this.database.ledger,this.database.compMonthlySettlements,async()=>{
      await this.database.ledger.where('ledgerOrigin').equals('SYSTEM').delete()
      const manual=new Map((await this.database.ledger.where('ledgerOrigin').equals('MANUAL').toArray()).map(x=>[x.id,x]))
      for(const entry of entries){
        if(entry.ledgerOrigin==='MANUAL'&&entry.id&&manual.has(entry.id))await this.database.ledger.update(entry.id,{compBalance:entry.compBalance,annualBalance:entry.annualBalance,monthlyCompBalance:entry.monthlyCompBalance,annualCompBalance:entry.annualCompBalance})
        else if(entry.ledgerOrigin==='SYSTEM')await this.database.ledger.add({...entry,id:undefined})
      }
      await this.database.compMonthlySettlements.clear();if(settlements.length)await this.database.compMonthlySettlements.bulkAdd(settlements)
    })
  }
  async currentBalances(){const last=(await this.all()).at(-1);return {compBalanceMinutes:last?.compBalance??0,annualBalanceMinutes:last?.annualBalance??0}}
  async currentCompBalances(){const last=(await this.all()).at(-1);return {monthly:last?.monthlyCompBalance??0,annual:last?.annualCompBalance??0,total:(last?.monthlyCompBalance??0)+(last?.annualCompBalance??0)}}
  entriesForRange(start:string,end:string):Promise<LedgerEntry[]>{return this.database.ledger.where('entryDate').between(start,end,true,true).sortBy('transactionDatetime')}
}

export class DexieCompPolicyRepository implements CompPolicyRepository{
  constructor(private database:WorkTimeDatabase){}
  async history(){return this.database.compPolicies.orderBy('effectiveFrom').toArray()}
  async current(){return (await this.history()).at(-1)}
  async policyOn(date:string){return (await this.history()).filter(x=>x.effectiveFrom<=date).at(-1)}
  async save(policy:CompSettlementPolicy){const old=await this.database.compPolicies.where('effectiveFrom').equals(policy.effectiveFrom).first();return this.database.compPolicies.put(old?{...policy,id:old.id}:policy)}
}
export class DexieCompCycleRepository implements CompCycleRepository{
  constructor(private database:WorkTimeDatabase){}
  all(){return this.database.compLeaveCycles.orderBy('startDate').toArray()}
  async upsert(cycle:LeaveCycle){const old=await this.database.compLeaveCycles.where('[startDate+endDate]').equals([cycle.startDate,cycle.endDate]).first();return this.database.compLeaveCycles.put(old?{...cycle,id:old.id}:cycle)}
}
export class DexieCompMonthlySettlementRepository implements CompMonthlySettlementRepository{
  constructor(private database:WorkTimeDatabase){}
  async all(){return (await this.database.compMonthlySettlements.toArray()).sort((a,b)=>b.year-a.year||b.month-a.month)}
  async forYear(year:number){return (await this.all()).filter(x=>x.year===year)}
  forMonth(year:number,month:number){return this.database.compMonthlySettlements.where('[year+month]').equals([year,month]).first()}
  async replaceDerived(values:CompMonthlySettlement[]){await this.database.transaction('rw',this.database.compMonthlySettlements,async()=>{await this.database.compMonthlySettlements.clear();if(values.length)await this.database.compMonthlySettlements.bulkAdd(values)})}
}

export class DexieSpecialDateRepository implements SpecialDateRepository {
  constructor(private database: WorkTimeDatabase) {}

  async all(): Promise<CalendarOverride[]> {
    return (await this.database.calendarOverrides.orderBy('workDate').toArray()).map(normalizeOverride)
  }

  async get(date: string): Promise<CalendarOverride | undefined> {
    const value=await this.database.calendarOverrides.where('workDate').equals(date).first();return value?normalizeOverride(value):undefined
  }

  async save(value: CalendarOverride): Promise<number> {
    const found = await this.database.calendarOverrides
      .where('workDate')
      .equals(value.workDate)
      .first()
    const normalized=normalizeOverride(value),savedValue = found ? { ...normalized, id: found.id } : normalized

    return this.database.calendarOverrides.put(savedValue)
  }

  async deleteByDate(date: string): Promise<void> {
    await this.database.calendarOverrides.where('workDate').equals(date).delete()
  }
}

export class DexieHolidayRepository implements HolidayRepository {
  constructor(private database: WorkTimeDatabase) {}

  forYear(year: number): Promise<OfficialHoliday[]> {
    return this.database.officialHolidays.where('year').equals(year).toArray()
  }

  get(date: string): Promise<OfficialHoliday | undefined> {
    return this.database.officialHolidays
      .where('holidayDate')
      .equals(date)
      .first()
  }

  async replaceYear(year: number, values: OfficialHoliday[]): Promise<void> {
    validateHolidayYear(year,values)
    await this.database.transaction('rw', this.database.officialHolidays, async () => {
      await this.database.officialHolidays.where('year').equals(year).delete()
      await this.database.officialHolidays.bulkPut(values)
    })
  }
}
