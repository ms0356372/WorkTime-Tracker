export interface YearMonth {year:number;month:number}
export function previousMonth({year,month}:YearMonth):YearMonth{return month===1?{year:year-1,month:12}:{year,month:month-1}}
export function nextMonth({year,month}:YearMonth):YearMonth{return month===12?{year:year+1,month:1}:{year,month:month+1}}
function daysInMonth(year:number,month:number){return new Date(Date.UTC(year,month,0)).getUTCDate()}
export function safeSettlementDate(year:number,month:number,day:number){return `${year}-${String(month).padStart(2,'0')}-${String(Math.min(day,daysInMonth(year,month))).padStart(2,'0')}`}
