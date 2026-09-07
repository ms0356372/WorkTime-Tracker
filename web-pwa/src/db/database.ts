import Dexie, { type EntityTable } from 'dexie'
import type { CalendarOverride, CompMonthlySettlement, CompSettlementPolicy, LedgerEntry, LeaveCycle, OfficialHoliday, Setting, WorkRecord } from '../models/domain'

export const DATABASE_SCHEMA_VERSION = 2
type StoredEntity<T extends { id?: number }> = Omit<T, 'id'> & { id: number }

export class WorkTimeDatabase extends Dexie {
  workRecords!:EntityTable<StoredEntity<WorkRecord>,'id'>; settings!:EntityTable<Setting,'key'>; ledger!:EntityTable<StoredEntity<LedgerEntry>,'id'>
  leaveCycles!:EntityTable<LeaveCycle,'id'>; compLeaveCycles!:EntityTable<LeaveCycle,'id'>
  calendarOverrides!:EntityTable<StoredEntity<CalendarOverride>,'id'>; officialHolidays!:EntityTable<OfficialHoliday,'holidayDate'>
  compPolicies!:EntityTable<CompSettlementPolicy,'id'>; compMonthlySettlements!:EntityTable<CompMonthlySettlement,'id'>
  appMetadata!:EntityTable<Setting,'key'>
  constructor(databaseName = 'worktime-tracker-pwa'){super(databaseName);this.version(1).stores({
    workRecords:'++id,&workDate',settings:'&key,effectiveDate',ledger:'++id,entryDate,transactionDatetime,transactionType,ledgerOrigin,sourceRecordId,reversalOfId',
    leaveCycles:'++id,&[startDate+endDate]',compLeaveCycles:'++id,&[startDate+endDate]',calendarOverrides:'++id,&workDate',
    officialHolidays:'&holidayDate,year',compPolicies:'++id,&effectiveFrom',compMonthlySettlements:'++id,&[year+month]',appMetadata:'&key'
  });this.version(DATABASE_SCHEMA_VERSION).stores({
    workRecords:'++id,&workDate',settings:'&key,effectiveDate',ledger:'++id,entryDate,transactionDatetime,transactionType,ledgerOrigin,sourceRecordId,reversalOfId',
    leaveCycles:'++id,&[startDate+endDate]',compLeaveCycles:'++id,&[startDate+endDate]',calendarOverrides:'++id,&workDate,category',
    officialHolidays:'&holidayDate,year',compPolicies:'++id,&effectiveFrom',compMonthlySettlements:'++id,&[year+month]',appMetadata:'&key'
  }).upgrade(async transaction => {
    await transaction.table('calendarOverrides').toCollection().modify(row => {
      if (!row.category) row.category = row.dayType === 'WORKDAY' ? 'COMPANY_MAKEUP_WORKDAY' : 'SPECIAL_NON_WORKDAY'
    })
  })}
}
export const db = new WorkTimeDatabase()
