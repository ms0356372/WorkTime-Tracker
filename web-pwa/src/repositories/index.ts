import { db } from '../db/database'
import { DexieWorkRecordRepository } from './dexieRepositories'

export const workRecordRepository = new DexieWorkRecordRepository(db)
