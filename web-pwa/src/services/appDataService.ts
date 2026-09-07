import { holidayRepository, settingsRepository, specialDateRepository } from '../repositories'
import { CalendarService } from './calendarService'
import { loadPackagedHolidayYear } from './holidayService'

export const DEFAULT_DAILY_MINUTES = 480
export async function loadCalendar(years:number[]):Promise<CalendarService>{
  const unique=[...new Set(years)]
  await Promise.all(unique.map(async year=>{try{await loadPackagedHolidayYear(year,holidayRepository)}catch{/* Preserve and use an existing cache on load failure. */}}))
  const [overrides, holidayGroups]=await Promise.all([specialDateRepository.all(),Promise.all(unique.map((year)=>holidayRepository.forYear(year)))])
  return new CalendarService(overrides,holidayGroups.flat())
}
export async function loadAnalysisSettings(today:string){
  const standard=Number(await settingsRepository.get('daily_standard_minutes',String(DEFAULT_DAILY_MINUTES)))
  let start=await settingsRepository.get('work_tracking_start_date')
  if(!start){start=today;await settingsRepository.set({key:'work_tracking_start_date',value:start})}
  return {dailyStandardMinutes:Number.isInteger(standard)&&standard>0?standard:DEFAULT_DAILY_MINUTES,calculationStartDate:start}
}
