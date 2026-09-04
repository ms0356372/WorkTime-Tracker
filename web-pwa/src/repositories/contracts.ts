import type { CalendarOverride, ISODate, LedgerEntry, OfficialHoliday, Setting, WorkRecord } from '../models/domain'
export interface WorkRecordRepository { save(record:WorkRecord):Promise<number>; getById(id:number):Promise<WorkRecord|undefined>; getByDate(date:ISODate):Promise<WorkRecord|undefined>; recordsForMonth(year:number,month:number):Promise<WorkRecord[]>; recent(limit?:number):Promise<WorkRecord[]>; delete(id:number):Promise<void> }
export interface SettingsRepository { get(key:string, fallback?:string):Promise<string|undefined>; set(setting:Setting):Promise<void> }
export interface LedgerRepository { all():Promise<LedgerEntry[]>; add(entry:LedgerEntry):Promise<number> }
export interface SpecialDateRepository { all():Promise<CalendarOverride[]>; save(value:CalendarOverride):Promise<number>; deleteByDate(date:string):Promise<void> }
export interface HolidayRepository { forYear(year:number):Promise<OfficialHoliday[]> }
/** A future sync adapter consumes these contracts; React never depends on Dexie directly. */
export interface RepositoryBundle { records:WorkRecordRepository; settings:SettingsRepository; ledger:LedgerRepository; specialDates:SpecialDateRepository; holidays:HolidayRepository }
