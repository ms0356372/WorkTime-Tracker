import 'fake-indexeddb/auto'
import { afterEach, describe, expect, it } from 'vitest'
import { WorkTimeDatabase } from '../db/database'
import type { CalendarOverride, LedgerEntry, WorkRecord } from '../models/domain'
import {
  DexieLedgerRepository,
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

  it('updates by ID without leaving the old date behind', async () => {
    const database=createDatabase(),repository=new DexieWorkRecordRepository(database)
    const id=await repository.save(workRecord())
    await repository.save({...workRecord('moved'),id,workDate:'2026-10-01'})
    expect(await repository.getByDate('2026-09-04')).toBeUndefined()
    expect((await repository.getById(id))?.note).toBe('moved')
    expect(await database.workRecords.count()).toBe(1)
  })

  it('deletes a record',async()=>{const database=createDatabase(),repository=new DexieWorkRecordRepository(database);const id=await repository.save(workRecord());await repository.delete(id);expect(await database.workRecords.count()).toBe(0)})

  it('queries a calendar month in newest-first order',async()=>{const repository=new DexieWorkRecordRepository(createDatabase());await repository.save({...workRecord(),workDate:'2026-08-31'});await repository.save({...workRecord(),workDate:'2026-09-01'});await repository.save({...workRecord(),workDate:'2026-09-30'});await repository.save({...workRecord(),workDate:'2026-10-01'});expect((await repository.recordsForMonth(2026,9)).map(row=>row.workDate)).toEqual(['2026-09-30','2026-09-01'])})

  it('returns only the newest requested recent records',async()=>{const repository=new DexieWorkRecordRepository(createDatabase());const dates:WorkRecord['workDate'][]=['2026-09-01','2026-09-03','2026-09-02'];for(const workDate of dates)await repository.save({...workRecord(),workDate});expect((await repository.recent(2)).map(row=>row.workDate)).toEqual(['2026-09-03','2026-09-02'])})
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
})
