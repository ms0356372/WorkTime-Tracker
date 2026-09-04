import { useCallback, useEffect, useState } from 'react'
import type { WorkRecord } from '../models/domain'
import { workRecordRepository } from '../repositories'

export const WORK_RECORDS_CHANGED = 'worktime:records-changed'
export function announceWorkRecordsChanged():void { window.dispatchEvent(new Event(WORK_RECORDS_CHANGED)) }

export function useWorkRecords(query:()=>Promise<WorkRecord[]>, dependencies:readonly unknown[]=[]):{records:WorkRecord[];loading:boolean;reload:()=>Promise<void>} {
  const [records,setRecords]=useState<WorkRecord[]>([])
  const [loading,setLoading]=useState(true)
  const reload=useCallback(async()=>{setLoading(true);try{setRecords(await query())}finally{setLoading(false)}},dependencies)
  useEffect(()=>{void reload();const listener=()=>{void reload()};window.addEventListener(WORK_RECORDS_CHANGED,listener);return()=>window.removeEventListener(WORK_RECORDS_CHANGED,listener)},[reload])
  return {records,loading,reload}
}

export function useRecentWorkRecords(limit=7){return useWorkRecords(()=>workRecordRepository.recent(limit),[limit])}
