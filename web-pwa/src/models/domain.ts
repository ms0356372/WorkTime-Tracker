/** ISO dates/times keep persistence timezone-neutral; all durations are integer minutes. */
export type ISODate = `${number}-${number}-${number}`
export type WorkdayType = '正常工作日'|'休息日'|'假日'|'補休'|'特休'|'其他'
export type LeaveType = 'COMP_TIME'|'ANNUAL_LEAVE'
export type DeductionPriority = 'COMP_TIME_FIRST'|'ANNUAL_LEAVE_FIRST'
export type CalendarDayType = 'WORKDAY'|'NON_WORKDAY'
export type TransactionType = 'WORKTIME_EARN'|'WORKTIME_DEDUCTION'|'MONTHLY_SETTLEMENT'|'LEAVE_CONVERSION'|'REVERSAL'|'ADJUSTMENT'|'MISSING_WORKDAY_DEDUCTION'|'ANNUAL_LEAVE_GRANT'|'ANNUAL_LEAVE_SETTLEMENT'|'COMP_LEAVE_SETTLEMENT'|'COMP_MONTHLY_TRANSFER'|'COMP_MONTHLY_CASH_SETTLEMENT'
export interface WorkRecord { id?:number; workDate:ISODate; clockIn?:string; clockOut?:string; breakStart?:string; breakEnd?:string; deductBreak:boolean; standardMinutes:number; note:string; workdayType:WorkdayType; overnight:boolean }
export interface Setting { key:string; value:string; effectiveDate?:ISODate }
export interface LedgerEntry { id?:number; entryDate:ISODate; entryType:string; reason:string; compChange:number; annualChange:number; compBalance:number; annualBalance:number; sourceRecordId?:number; transactionDatetime:string; transactionType:TransactionType; ledgerOrigin:'SYSTEM'|'MANUAL'; sourceLeaveType?:LeaveType; targetLeaveType?:LeaveType; sourceMinutes?:number; targetMinutes?:number; note:string; createdAt:string; reversalOfId?:number; monthlyCompBalance:number; annualCompBalance:number; cashAmountCents:number; cashHourlyRateCents:number }
export interface LeaveCycle { id?:number; startDate:ISODate; endDate:ISODate; totalMinutes?:number }
export interface CalendarOverride { id?:number; workDate:ISODate; dayType:CalendarDayType; note:string; createdAt:string; updatedAt:string }
export interface OfficialHoliday { holidayDate:ISODate; name:string; year:number; source:string; syncedAt:string }
export interface CompSettlementPolicy { id?:number; effectiveFrom:ISODate; mode:'ANNUAL'|'MONTHLY'; monthlyCapMinutes:number; cashHourlyRateCents:number; createdAt:string }
export interface CompMonthlySettlement { id?:number; year:number; month:number; preMonthlyBalance:number; annualBalanceBefore:number; monthlyCapMinutes:number; transferToAnnualMinutes:number; cashMinutes:number; cashHourlyRateCents:number; cashAmountCents:number; annualBalanceAfter:number; monthlyBalanceAfter:number; policyEffectiveFrom:ISODate; annualSettlementOccurred:boolean }
