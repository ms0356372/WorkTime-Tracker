import type { HolidayRepository, SettingsRepository } from '../repositories/contracts'
import type { ISODate, OfficialHoliday } from '../models/domain'

interface PackagedHoliday {holidayDate?:string;date?:string;name:string;year?:number;source?:string}
interface PackagedHolidayFile {year:number;source:string;holidays:PackagedHoliday[]}
const ISO_DATE=/^\d{4}-(0[1-9]|1[0-2])-([0-2]\d|3[01])$/
export function validateHolidayYear(year:number,values:OfficialHoliday[]):OfficialHoliday[]{
  const dates=new Set<string>()
  for(const value of values){
    const [dateYear,dateMonth,dateDay]=value.holidayDate.split('-').map(Number),parsed=new Date(dateYear,dateMonth-1,dateDay)
    const invalidDate=parsed.getFullYear()!==dateYear||parsed.getMonth()!==dateMonth-1||parsed.getDate()!==dateDay
    if(!ISO_DATE.test(value.holidayDate)||invalidDate||dateYear!==year||value.year!==year||!value.name.trim()||dates.has(value.holidayDate))throw new Error('假日資料驗證失敗，未更新現有快取。')
    dates.add(value.holidayDate)
  }
  if(!values.length)throw new Error('假日資料不可為空，未更新現有快取。')
  return values
}
export function parseHolidayPackage(input:unknown,syncedAt:string):{year:number;values:OfficialHoliday[]}{
  if(typeof input!=='object'||input===null||!('year'in input)||!('source'in input)||!('holidays'in input))throw new Error('假日資料格式不正確。')
  const file=input as PackagedHolidayFile
  if(!Number.isInteger(file.year)||typeof file.source!=='string'||!Array.isArray(file.holidays))throw new Error('假日資料格式不正確。')
  const values=file.holidays.map(item=>({holidayDate:(item.holidayDate??item.date??'') as ISODate,name:item.name,year:item.year??file.year,source:item.source??file.source,syncedAt}))
  return {year:file.year,values:validateHolidayYear(file.year,values)}
}
export async function loadPackagedHolidayYear(year:number,repository:HolidayRepository,fetcher:typeof fetch=fetch,force=false):Promise<OfficialHoliday[]>{
  const cached=await repository.forYear(year);if(cached.length&&!force)return cached
  const response=await fetcher(`${import.meta.env.BASE_URL}data/holidays/${year}.json`);if(!response.ok)throw new Error(`${year} 年套裝假日資料無法載入。`)
  const parsed=parseHolidayPackage(await response.json(),new Date().toISOString())
  if(parsed.year!==year)throw new Error('假日資料年度不符，未更新現有快取。')
  await repository.replaceYear(year,parsed.values);return parsed.values
}
export async function updatePackagedHolidayYear(year:number,repository:HolidayRepository,settings:SettingsRepository,fetcher:typeof fetch=fetch):Promise<OfficialHoliday[]>{
  const values=await loadPackagedHolidayYear(year,repository,fetcher,true)
  await settings.set({key:`holiday_updated_${year}`,value:new Date().toISOString()});return values
}
