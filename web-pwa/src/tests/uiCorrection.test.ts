import {describe,expect,it} from 'vitest'
import {annualLeaveHoursToMinutes,annualLeaveMinutesToHours} from '../services/settingsUiService'
import {completeRecordEdit} from '../services/editNavigationService'

describe('annual leave settings UI units',()=>{
  it('displays stored integer minutes as hours',()=>expect(annualLeaveMinutesToHours(14400)).toBe(240))
  it('converts entered hours back to stored minutes',()=>expect(annualLeaveHoursToMinutes(240)).toBe(14400))
  it('accepts zero and decimal hours that produce whole minutes',()=>{expect(annualLeaveHoursToMinutes(0)).toBe(0);expect(annualLeaveHoursToMinutes(1.1)).toBe(66)})
  it.each([-1,Number.NaN,Number.POSITIVE_INFINITY,1.111])('rejects invalid hour value %s',value=>expect(()=>annualLeaveHoursToMinutes(value)).toThrow())
})

describe('record edit navigation',()=>{
  it('returns a calendar edit to its month and scroll position',()=>expect(completeRecordEdit({year:2026,month:9,scrollY:320})).toEqual({page:'calendar',view:{year:2026,month:9,scrollY:320}}))
  it('keeps Records-origin and missing-origin edits in Records',()=>expect(completeRecordEdit()).toEqual({page:'records'}))
})
