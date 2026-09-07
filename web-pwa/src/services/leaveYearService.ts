import type {ISODate,LeaveCycle} from '../models/domain'
import {safeSettlementDate} from '../utils/date'

function addDay(value:string,days:number):ISODate{const [y,m,d]=value.split('-').map(Number),date=new Date(Date.UTC(y,m-1,d+days));return `${date.getUTCFullYear()}-${String(date.getUTCMonth()+1).padStart(2,'0')}-${String(date.getUTCDate()).padStart(2,'0')}` as ISODate}
export function getCurrentLeaveCycle(today:ISODate,month:number,day:number,totalMinutes=0):LeaveCycle{
  const year=Number(today.slice(0,4)),settlement=safeSettlementDate(year,month,day) as ISODate
  if(today<=settlement)return {startDate:addDay(safeSettlementDate(year-1,month,day),1),endDate:settlement,totalMinutes}
  return {startDate:addDay(settlement,1),endDate:safeSettlementDate(year+1,month,day) as ISODate,totalMinutes}
}
export function parseSettlement(value:string,_today:ISODate):{month:number;day:number}{const parts=value.split('-').map(Number);return parts.length===3?{month:parts[1],day:parts[2]}:{month:12,day:31}}
