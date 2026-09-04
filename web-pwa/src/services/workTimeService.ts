import type { WorkRecord } from '../models/domain'
import { timeToMinutes } from '../utils/time'

export interface WorkTimeResult { actualWorkMinutes:number; overtimeMinutes:number; shortfallMinutes:number }

export function calculateOverlapMinutes(workStart:number,workEnd:number,breakStart:number,breakEnd:number):number {
  if (breakEnd < breakStart) throw new Error('午休結束時間不可早於開始時間。')
  return Math.max(0, Math.min(workEnd, breakEnd) - Math.max(workStart, breakStart))
}

export function calculateWorkMinutes(record:WorkRecord):number {
  if (!record.clockIn || !record.clockOut) throw new Error('請輸入上班與下班時間。')
  const start=timeToMinutes(record.clockIn)
  let end=timeToMinutes(record.clockOut)
  if(end<start){if(!record.overnight)throw new Error('下班時間不可早於上班時間，若為跨日班請開啟跨日班。');end+=1440}
  let overlap=0
  if(record.deductBreak&&record.breakStart&&record.breakEnd){
    const breakStart=timeToMinutes(record.breakStart),breakEnd=timeToMinutes(record.breakEnd)
    overlap=calculateOverlapMinutes(start,end,breakStart,breakEnd)
  }
  return Math.max(end-start-overlap,0)
}
export function calculateDailyDifference(actualMinutes:number,standardMinutes:number):number {if(standardMinutes<0)throw new Error('每日標準工時不可為負數。');return actualMinutes-standardMinutes}
export function calculateWorkTime(record:WorkRecord):WorkTimeResult {const actualWorkMinutes=calculateWorkMinutes(record);const difference=calculateDailyDifference(actualWorkMinutes,record.standardMinutes);return {actualWorkMinutes,overtimeMinutes:Math.max(difference,0),shortfallMinutes:Math.max(-difference,0)}}
