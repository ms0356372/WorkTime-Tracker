import Dexie, { type EntityTable } from 'dexie'
import type { CalendarOverride, CompMonthlySettlement, CompSettlementPolicy, LedgerEntry, LeaveCycle, OfficialHoliday, Setting, WorkRecord } from '../models/domain'

export const DATABASE_SCHEMA_VERSION = 1
export class WorkTimeDatabase extends Dexie {
  workRecords!:EntityTable<WorkRecord,'id'>; settings!:EntityTable<Setting,'key'>; ledger!:EntityTable<LedgerEntry,'id'>
  leaveCycles!:EntityTable<LeaveCycle,'id'>; compLeaveCycles!:EntityTable<LeaveCycle,'id'>
  calendarOverrides!:EntityTable<CalendarOverride,'id'>; officialHolidays!:EntityTable<OfficialHoliday,'holidayDate'>
  compPolicies!:EntityTable<CompSettlementPolicy,'id'>; compMonthlySettlements!:EntityTable<CompMonthlySettlement,'id'>
  appMetadata!:EntityTable<Setting,'key'>
  constructor(){super('worktime-tracker-pwa');this.version(DATABASE_SCHEMA_VERSION).stores({
    workRecords:'++id,&workDate',settings:'&key,effectiveDate',ledger:'++id,entryDate,transactionDatetime,transactionType,ledgerOrigin,sourceRecordId,reversalOfId',
    leaveCycles:'++id,&[startDate+endDate]',compLeaveCycles:'++id,&[startDate+endDate]',calendarOverrides:'++id,&workDate',
    officialHolidays:'&holidayDate,year',compPolicies:'++id,&effectiveFrom',compMonthlySettlements:'++id,&[year+month]',appMetadata:'&key'
  })}
}
export const db = new WorkTimeDatabase()
