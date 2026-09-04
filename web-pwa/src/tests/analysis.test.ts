import {describe,expect,it} from 'vitest'
import type {WorkRecord} from '../models/domain'
import {summarize} from '../services/analysisService'
const record=(workDate:WorkRecord['workDate'],clockOut:string):WorkRecord=>({workDate,clockIn:'09:00',clockOut,breakStart:'12:00',breakEnd:'13:00',deductBreak:true,standardMinutes:480,note:'',workdayType:'正常工作日',overnight:false})
describe('monthly summary',()=>{it('totals work, attendance, average, overtime and shortfall',()=>{expect(summarize([record('2026-09-01','18:00'),record('2026-09-02','19:00'),record('2026-09-03','17:00')])).toMatchObject({workMinutes:1440,workdays:3,averageMinutes:480,overtimeMinutes:60,shortfallMinutes:60})})})
