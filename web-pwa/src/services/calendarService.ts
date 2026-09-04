import type { CalendarOverride, ISODate, OfficialHoliday } from '../models/domain'

export type WorkdaySource = 'SPECIAL_OVERRIDE' | 'OFFICIAL_HOLIDAY' | 'WEEKDAY' | 'WEEKEND'
export interface WorkdayReason { isWorkday:boolean; source:WorkdaySource; label:string; note?:string }

export function localISODate(value = new Date()): ISODate {
  const year = value.getFullYear(), month = String(value.getMonth() + 1).padStart(2, '0'), day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}` as ISODate
}

function localWeekday(date: string): number {
  const [year, month, day] = date.split('-').map(Number)
  return new Date(year, month - 1, day).getDay()
}

export class CalendarService {
  private overrides = new Map<string, CalendarOverride>()
  private holidays = new Map<string, OfficialHoliday>()
  private reliableYears = new Set<number>()

  constructor(overrides:CalendarOverride[] = [], holidays:OfficialHoliday[] = []) { this.update(overrides, holidays) }
  update(overrides:CalendarOverride[], holidays:OfficialHoliday[]) {
    this.overrides = new Map(overrides.map((row) => [row.workDate, row]))
    this.holidays = new Map(holidays.map((row) => [row.holidayDate, row]))
    this.reliableYears = new Set(holidays.map((row) => row.year))
  }
  hasHolidayData(year:number) { return this.reliableYears.has(year) }
  getWorkdayReason(date:string):WorkdayReason {
    const override = this.overrides.get(date)
    if (override) return { isWorkday: override.dayType === 'WORKDAY', source:'SPECIAL_OVERRIDE', label:override.dayType === 'WORKDAY' ? '特殊工作日' : '特殊非工作日', note:override.note }
    const holiday = this.holidays.get(date)
    if (holiday) return { isWorkday:false, source:'OFFICIAL_HOLIDAY', label:holiday.name || '國定假日', note:holiday.name }
    const weekday = localWeekday(date)
    return weekday > 0 && weekday < 6 ? { isWorkday:true, source:'WEEKDAY', label:'工作日' } : { isWorkday:false, source:'WEEKEND', label:'週末' }
  }
  isWorkday(date:string) { return this.getWorkdayReason(date).isWorkday }
  standardMinutesFor(date:string, dailyStandardMinutes:number) { return this.isWorkday(date) ? dailyStandardMinutes : 0 }
}
