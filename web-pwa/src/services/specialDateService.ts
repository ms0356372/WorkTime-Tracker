import type { CalendarDayType, CalendarOverride, SpecialDateCategory } from '../models/domain'

export const SPECIAL_DATE_LABELS:Record<SpecialDateCategory,string>={
  COMPANY_MAKEUP_WORKDAY:'公司補班日',COMPANY_HOLIDAY:'公司假日',SPECIAL_NON_WORKDAY:'特殊非工作日'
}
export function categoryToDayType(category:SpecialDateCategory):CalendarDayType{return category==='COMPANY_MAKEUP_WORKDAY'?'WORKDAY':'NON_WORKDAY'}
export function normalizeOverride(value:CalendarOverride):CalendarOverride & {category:SpecialDateCategory}{
  const category=value.category??(value.dayType==='WORKDAY'?'COMPANY_MAKEUP_WORKDAY':'SPECIAL_NON_WORKDAY')
  return {...value,category,dayType:categoryToDayType(category)}
}
