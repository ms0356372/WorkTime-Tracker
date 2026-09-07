import { db } from '../db/database'
import { DexieHolidayRepository, DexieSettingsRepository, DexieSpecialDateRepository, DexieWorkRecordRepository } from './dexieRepositories'
import { createWorkRecordMutations } from '../services/workRecordMutations'

export const recordsRepository = new DexieWorkRecordRepository(db)
export const settingsRepository = new DexieSettingsRepository(db)
export const specialDateRepository = new DexieSpecialDateRepository(db)
export const holidayRepository = new DexieHolidayRepository(db)
export const workRecordMutations = createWorkRecordMutations(recordsRepository)
