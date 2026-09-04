import type { CalendarOverride, LedgerEntry, OfficialHoliday, Setting, WorkRecord } from '../models/domain'
export interface WorkRecordRepository { save(record:WorkRecord):Promise<number>; getByDate(date:string):Promise<WorkRecord|undefined>; recordsForMonth(year:number,month:number):Promise<WorkRecord[]>; recent(limit?:number):Promise<WorkRecord[]>; delete(id:number):Promise<void> }
export interface SettingsRepository { get(key:string, fallback?:string):Promise<string|undefined>; set(setting:Setting):Promise<void> }
export interface LedgerRepository { all():Promise<LedgerEntry[]>; add(entry:LedgerEntry):Promise<number> }
export interface SpecialDateRepository { get(date:string):Promise<CalendarOverride|undefined>; all():Promise<CalendarOverride[]>; save(value:CalendarOverride):Promise<number>; deleteByDate(date:string):Promise<void> }
export interface HolidayRepository { get(date:string):Promise<OfficialHoliday|undefined>; forYear(year:number):Promise<OfficialHoliday[]>; replaceYear(year:number, values:OfficialHoliday[]):Promise<void> }
/** A future sync adapter consumes these contracts; React never depends on Dexie directly. */
export interface RepositoryBundle { records:WorkRecordRepository; settings:SettingsRepository; ledger:LedgerRepository; specialDates:SpecialDateRepository; holidays:HolidayRepository }
