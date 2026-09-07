import 'fake-indexeddb/auto'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {WorkTimeDatabase} from '../db/database'
import type {OfficialHoliday,WorkRecord} from '../models/domain'
import {DexieHolidayRepository,DexieSettingsRepository,DexieWorkRecordRepository} from '../repositories/dexieRepositories'
import {CalendarService} from '../services/calendarService'
import {parseHolidayPackage,updatePackagedHolidayYear,validateHolidayYear} from '../services/holidayService'
import {categoryToDayType,normalizeOverride} from '../services/specialDateService'
import {createWorkRecordMutations,WORK_RECORDS_CHANGED} from '../services/workRecordMutations'
import {summarizeMonth} from '../services/analysisService'

const databases:WorkTimeDatabase[]=[]
function setup(){const database=new WorkTimeDatabase(`phase4-${crypto.randomUUID()}`);databases.push(database);return {database,records:new DexieWorkRecordRepository(database),holidays:new DexieHolidayRepository(database)}}
afterEach(async()=>{await Promise.all(databases.splice(0).map(database=>database.delete()))})
const record=(workDate:WorkRecord['workDate'],clockOut='17:00'):WorkRecord=>({workDate,clockIn:'08:00',clockOut,breakStart:'12:00',breakEnd:'13:00',deductBreak:true,standardMinutes:480,note:'',workdayType:'正常工作日',overnight:false})
const official=(date:OfficialHoliday['holidayDate'],name='假日'):OfficialHoliday=>({holidayDate:date,name,year:Number(date.slice(0,4)),source:'TEST',syncedAt:'now'})

describe('Home persisted-date semantics',()=>{
  it('today lookup is independent from the newest record',async()=>{const {records}=setup();await records.save(record('2026-09-07'));await records.save(record('2026-09-08','18:00'));expect(await records.getByDate('2026-09-07')).toMatchObject({workDate:'2026-09-07',clockOut:'17:00'})})
  it('returns no record when today is absent',async()=>{const {records}=setup();await records.save(record('2026-09-06'));expect(await records.getByDate('2026-09-07')).toBeUndefined()})
  it('yesterday does not enter the selected day but remains in the month total',()=>{const calendar=new CalendarService([], [official('2026-09-25')]);const summary=summarizeMonth([record('2026-09-06'),record('2026-09-07')],calendar,{year:2026,month:9,dailyStandardMinutes:480,calculationStartDate:'2026-09-07',today:'2026-09-07'});expect(summary.workMinutes).toBe(960)})
})

describe('special-date presentation mapping',()=>{
  it.each([['COMPANY_MAKEUP_WORKDAY','WORKDAY'],['COMPANY_HOLIDAY','NON_WORKDAY'],['SPECIAL_NON_WORKDAY','NON_WORKDAY']] as const)('%s maps to %s',(category,dayType)=>expect(categoryToDayType(category)).toBe(dayType))
  it('normalizes readable legacy override data conservatively',()=>expect(normalizeOverride({workDate:'2026-09-07',dayType:'NON_WORKDAY',note:'legacy',createdAt:'x',updatedAt:'x'})).toMatchObject({category:'SPECIAL_NON_WORKDAY',dayType:'NON_WORKDAY'}))
})

describe('holiday validation and safe replacement',()=>{
  it('accepts a complete packaged holiday',()=>expect(parseHolidayPackage({year:2026,source:'DGPA',holidays:[{holidayDate:'2026-01-01',name:'元旦',year:2026,source:'DGPA'}]},'now').values).toHaveLength(1))
  it('rejects year mismatch, impossible dates and duplicate dates',()=>{expect(()=>validateHolidayYear(2026,[official('2027-01-01')])).toThrow();expect(()=>validateHolidayYear(2026,[official('2026-02-31')])).toThrow();expect(()=>validateHolidayYear(2026,[official('2026-01-01'),official('2026-01-01')])).toThrow()})
  it('replaceYear keeps a valid new annual result',async()=>{const {holidays}=setup();await holidays.replaceYear(2026,[official('2026-01-01')]);await holidays.replaceYear(2026,[official('2026-10-10','國慶日')]);expect(await holidays.forYear(2026)).toEqual([official('2026-10-10','國慶日')])})
  it('failed update leaves the previous cache intact',async()=>{const {holidays}=setup();const old=official('2026-01-01');await holidays.replaceYear(2026,[old]);const settings=new DexieSettingsRepository(databases.at(-1)!);await expect(updatePackagedHolidayYear(2026,holidays,settings,async()=>{throw new Error('offline')})).rejects.toThrow();expect(await holidays.forYear(2026)).toEqual([old])})
  it('holiday overrides weekday and special WORKDAY overrides holiday',()=>{const holiday=official('2026-09-07');expect(new CalendarService([], [holiday]).isWorkday('2026-09-07')).toBe(false);expect(new CalendarService([{workDate:'2026-09-07',category:'COMPANY_MAKEUP_WORKDAY',dayType:'WORKDAY',note:'',createdAt:'x',updatedAt:'x'}],[holiday]).isWorkday('2026-09-07')).toBe(true)})
})

describe('shared work-record mutation boundary',()=>{
  it('cancelled delete retains the record and emits nothing',async()=>{const {records}=setup(),events=new EventTarget(),listener=vi.fn();events.addEventListener(WORK_RECORDS_CHANGED,listener);const id=await records.save(record('2026-09-07'));const mutations=createWorkRecordMutations(records,{events,confirmDelete:()=>false});expect(await mutations.deleteWorkRecord({id,workDate:'2026-09-07'})).toBe(false);expect(await records.getByDate('2026-09-07')).toBeDefined();expect(listener).not.toHaveBeenCalled()})
  it('confirmed delete removes the record and emits exactly once',async()=>{const {records}=setup(),events=new EventTarget(),listener=vi.fn();events.addEventListener(WORK_RECORDS_CHANGED,listener);const id=await records.save(record('2026-09-07'));const mutations=createWorkRecordMutations(records,{events,confirmDelete:()=>true});expect(await mutations.deleteWorkRecord({id,workDate:'2026-09-07'})).toBe(true);expect(await records.getByDate('2026-09-07')).toBeUndefined();expect(listener).toHaveBeenCalledTimes(1)})
  it('save emits exactly once',async()=>{const {records}=setup(),events=new EventTarget(),listener=vi.fn();events.addEventListener(WORK_RECORDS_CHANGED,listener);await createWorkRecordMutations(records,{events}).saveWorkRecord(record('2026-09-07'));expect(listener).toHaveBeenCalledTimes(1)})
})
