import type { WorkTimeDatabase } from '../db/database'
import type { CalendarOverride, ISODate, LedgerEntry, OfficialHoliday, Setting, WorkRecord } from '../models/domain'
import type {
  HolidayRepository,
  LedgerRepository,
  SettingsRepository,
  SpecialDateRepository,
  WorkRecordRepository,
} from './contracts'
import { nextMonth } from '../utils/date'

export class DexieWorkRecordRepository implements WorkRecordRepository {
  constructor(private database: WorkTimeDatabase) {}

  async save(record: WorkRecord): Promise<number> {
    return this.database.transaction('rw', this.database.workRecords, async () => {
      const sameDate = await this.database.workRecords.where('workDate').equals(record.workDate).first()
      if (record.id !== undefined) {
        const original = await this.database.workRecords.get(record.id)
        if (original && sameDate && sameDate.id !== record.id) {
          await this.database.workRecords.delete(record.id)
          return this.database.workRecords.put({ ...record, id: sameDate.id })
        }
        if (original) return this.database.workRecords.put({ ...record, id: record.id })
      }
      return this.database.workRecords.put(sameDate ? { ...record, id: sameDate.id } : record)
    })
  }

  getById(id: number): Promise<WorkRecord | undefined> {
    return this.database.workRecords.get(id)
  }

  getByDate(date: ISODate): Promise<WorkRecord | undefined> {
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
}

export class DexieLedgerRepository implements LedgerRepository {
  constructor(private database: WorkTimeDatabase) {}

  all(): Promise<LedgerEntry[]> {
    return this.database.ledger.orderBy('transactionDatetime').toArray()
  }

  add(entry: LedgerEntry): Promise<number> {
    return this.database.ledger.add(entry)
  }
}

export class DexieSpecialDateRepository implements SpecialDateRepository {
  constructor(private database: WorkTimeDatabase) {}

  all(): Promise<CalendarOverride[]> {
    return this.database.calendarOverrides.orderBy('workDate').toArray()
  }

  async save(value: CalendarOverride): Promise<number> {
    const found = await this.database.calendarOverrides
      .where('workDate')
      .equals(value.workDate)
      .first()
    const savedValue = found ? { ...value, id: found.id } : value

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
}
