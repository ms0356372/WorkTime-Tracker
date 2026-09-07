import { db } from '../db/database'
import { DexieCompCycleRepository, DexieCompMonthlySettlementRepository, DexieCompPolicyRepository, DexieHolidayRepository, DexieLedgerRepository, DexieSettingsRepository, DexieSpecialDateRepository, DexieWorkRecordRepository } from './dexieRepositories'
import { createWorkRecordMutations } from '../services/workRecordMutations'

export const recordsRepository = new DexieWorkRecordRepository(db)
export const settingsRepository = new DexieSettingsRepository(db)
export const specialDateRepository = new DexieSpecialDateRepository(db)
export const holidayRepository = new DexieHolidayRepository(db)
export const ledgerRepository = new DexieLedgerRepository(db)
export const compPolicyRepository = new DexieCompPolicyRepository(db)
export const compCycleRepository = new DexieCompCycleRepository(db)
export const compMonthlySettlementRepository = new DexieCompMonthlySettlementRepository(db)
export const workRecordMutations = createWorkRecordMutations(recordsRepository)
