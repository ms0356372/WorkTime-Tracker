import 'fake-indexeddb/auto'
import { afterEach, describe, expect, it } from 'vitest'
import { WorkTimeDatabase } from '../db/database'
import type { CalendarOverride, LedgerEntry, WorkRecord } from '../models/domain'
import {
  DexieLedgerRepository,
  DexieHolidayRepository,
  DexieSettingsRepository,
  DexieSpecialDateRepository,
  DexieWorkRecordRepository,
} from '../repositories/dexieRepositories'

const databases: WorkTimeDatabase[] = []

function createDatabase(): WorkTimeDatabase {
  const database = new WorkTimeDatabase(`repository-test-${crypto.randomUUID()}`)
  databases.push(database)
  return database
}

afterEach(async () => {
  await Promise.all(databases.splice(0).map((database) => database.delete()))
})

const workRecord = (note = 'first'): WorkRecord => ({
  workDate: '2026-09-04',
  deductBreak: false,
  standardMinutes: 480,
  note,
  workdayType: '正常工作日',
  overnight: false,
})

const ledgerEntry = (): LedgerEntry => ({
  entryDate: '2026-09-04',
  entryType: 'worktime',
  reason: 'test',
  compChange: 30,
  annualChange: 0,
  compBalance: 30,
  annualBalance: 0,
  transactionDatetime: '2026-09-04T09:00:00',
  transactionType: 'WORKTIME_EARN',
  ledgerOrigin: 'SYSTEM',
  note: '',
  createdAt: '2026-09-04T09:00:00',
  monthlyCompBalance: 30,
  annualCompBalance: 0,
  cashAmountCents: 0,
  cashHourlyRateCents: 0,
})

const calendarOverride = (): CalendarOverride => ({
  workDate: '2026-09-04',
  dayType: 'NON_WORKDAY',
  note: 'special date',
  createdAt: '2026-09-04T09:00:00',
  updatedAt: '2026-09-04T09:00:00',
})

describe('DexieWorkRecordRepository', () => {
  it('returns the generated ID when inserting a work record', async () => {
    const repository = new DexieWorkRecordRepository(createDatabase())

    const id = await repository.save(workRecord())

    expect(id).toBeTypeOf('number')
    expect(id).toBeGreaterThan(0)
  })

  it('updates the existing record for the same date and returns its ID', async () => {
    const database = createDatabase()
    const repository = new DexieWorkRecordRepository(database)
    const firstId = await repository.save(workRecord())

    const secondId = await repository.save(workRecord('updated'))

    expect(secondId).toBe(firstId)
    expect(await database.workRecords.count()).toBe(1)
    expect((await repository.getByDate('2026-09-04'))?.note).toBe('updated')
  })
})

describe('DexieLedgerRepository', () => {
  it('returns the generated ID when appending an entry', async () => {
    const repository = new DexieLedgerRepository(createDatabase())

    const id = await repository.add(ledgerEntry())

    expect(id).toBeTypeOf('number')
    expect(id).toBeGreaterThan(0)
  })
})

describe('DexieSpecialDateRepository', () => {
  it('returns the generated ID when saving an override', async () => {
    const repository = new DexieSpecialDateRepository(createDatabase())

    const id = await repository.save(calendarOverride())

    expect(id).toBeTypeOf('number')
    expect(id).toBeGreaterThan(0)
  })

  it('updates the existing override for the same date', async () => {
    const database = createDatabase()
    const repository = new DexieSpecialDateRepository(database)
    const firstId = await repository.save(calendarOverride())

    const secondId = await repository.save({ ...calendarOverride(), note: 'updated' })

    expect(secondId).toBe(firstId)
    expect(await database.calendarOverrides.count()).toBe(1)
  })

  it('deletes an override by date', async () => { const repository=new DexieSpecialDateRepository(createDatabase());await repository.save(calendarOverride());await repository.deleteByDate('2026-09-04');expect(await repository.all()).toEqual([]) })
})

describe('holiday and settings repositories',()=>{
  it('replaces and queries an official holiday year',async()=>{const repository=new DexieHolidayRepository(createDatabase()),value={holidayDate:'2026-01-01' as const,name:'元旦',year:2026,source:'TEST',syncedAt:'now'};await repository.replaceYear(2026,[value]);expect(await repository.forYear(2026)).toEqual([value]);expect(await repository.get('2026-01-01')).toEqual(value)})
  it('persists settings and lunch as string values',async()=>{const repository=new DexieSettingsRepository(createDatabase());await repository.set({key:'daily_standard_minutes',value:'450'});await repository.setLunchBreak('12:10','13:00');expect(await repository.get('daily_standard_minutes')).toBe('450');expect(await repository.get('lunch_break_start')).toBe('12:10')})
})
