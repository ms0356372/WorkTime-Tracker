import { holidayRepository, settingsRepository, specialDateRepository } from '../repositories'
import { CalendarService } from './calendarService'

export const DEFAULT_DAILY_MINUTES = 480
export async function loadCalendar(years:number[]):Promise<CalendarService>{
  const [overrides, holidayGroups]=await Promise.all([specialDateRepository.all(),Promise.all([...new Set(years)].map((year)=>holidayRepository.forYear(year)))])
  return new CalendarService(overrides,holidayGroups.flat())
}
export async function loadAnalysisSettings(today:string){
  const standard=Number(await settingsRepository.get('daily_standard_minutes',String(DEFAULT_DAILY_MINUTES)))
  let start=await settingsRepository.get('work_tracking_start_date')
  if(!start){start=today;await settingsRepository.set({key:'work_tracking_start_date',value:start})}
  return {dailyStandardMinutes:Number.isInteger(standard)&&standard>0?standard:DEFAULT_DAILY_MINUTES,calculationStartDate:start}
}
