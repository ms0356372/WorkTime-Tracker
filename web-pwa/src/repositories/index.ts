import { db } from '../db/database'
import { DexieHolidayRepository, DexieSettingsRepository, DexieSpecialDateRepository, DexieWorkRecordRepository } from './dexieRepositories'

export const recordsRepository = new DexieWorkRecordRepository(db)
export const settingsRepository = new DexieSettingsRepository(db)
export const specialDateRepository = new DexieSpecialDateRepository(db)
export const holidayRepository = new DexieHolidayRepository(db)
