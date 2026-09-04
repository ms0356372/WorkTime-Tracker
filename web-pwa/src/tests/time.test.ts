import {describe,expect,it} from 'vitest'; import {formatMinutes,minutesToTime,timeToMinutes} from '../utils/time'; import {calculateWorkMinutes} from '../services/workTimeService'; import type {WorkRecord} from '../models/domain'
const record=(clockIn:string,clockOut:string,extra:Partial<WorkRecord>={}):WorkRecord=>({workDate:'2026-09-01',clockIn,clockOut,breakStart:'12:00',breakEnd:'13:00',deductBreak:true,standardMinutes:480,note:'',workdayType:'正常工作日',overnight:false,...extra})
describe('minute helpers',()=>{it('formats and converts integer minutes',()=>{expect(timeToMinutes('08:30')).toBe(510);expect(minutesToTime(510)).toBe('08:30');expect(formatMinutes(510)).toBe('8 小時 30 分')});it('rejects invalid time',()=>expect(()=>timeToMinutes('24:00')).toThrow())})
describe('Python-compatible basic calculation',()=>{it('deducts only lunch overlap',()=>{expect(calculateWorkMinutes(record('09:00','12:30'))).toBe(180);expect(calculateWorkMinutes(record('13:00','18:00'))).toBe(300)});it('supports explicit overnight',()=>expect(calculateWorkMinutes(record('22:00','06:00',{deductBreak:false,overnight:true}))).toBe(480));it('rejects implicit overnight',()=>expect(()=>calculateWorkMinutes(record('22:00','06:00',{deductBreak:false}))).toThrow())})
describe('work day outcomes',()=>{
  it('deducts a full lunch overlap',()=>expect(calculateWorkMinutes(record('08:00','17:30'))).toBe(510))
  it('deducts a partial lunch overlap',()=>expect(calculateWorkMinutes(record('08:00','12:30'))).toBe(240))
  it('does not deduct lunch without overlap',()=>expect(calculateWorkMinutes(record('13:30','18:00'))).toBe(270))
  it('calculates a normal day',()=>expect(calculateWorkMinutes(record('09:00','18:00'))).toBe(480))
  it('calculates overtime and shortfall',()=>{expect(calculateWorkMinutes(record('09:00','19:30'))-480).toBe(90);expect(480-calculateWorkMinutes(record('09:00','17:00'))).toBe(60)})
})
