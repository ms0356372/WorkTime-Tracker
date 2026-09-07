import type { WorkRecordRepository } from '../repositories/contracts'
import type { WorkRecord } from '../models/domain'
import {rebuildLedger} from './ledgerCoordinator'

export const WORK_RECORDS_CHANGED='work-records-changed'
export const workRecordEvents=new EventTarget()
export interface MutationOptions{events?:EventTarget;confirmDelete?:(message:string)=>boolean;rebuild?:()=>Promise<unknown>}
export function createWorkRecordMutations(repository:WorkRecordRepository,options:MutationOptions={}){
  const events=options.events??workRecordEvents,confirmDelete=options.confirmDelete??((message:string)=>window.confirm(message)),rebuild=options.rebuild??(options.events?async()=>{}:()=>rebuildLedger())
  const changed=()=>events.dispatchEvent(new Event(WORK_RECORDS_CHANGED))
  return {
    async saveWorkRecord(record:WorkRecord){const previous=await repository.getByDate(record.workDate),id=await repository.save(record);try{await rebuild()}catch{if(previous)await repository.save(previous);else await repository.delete(id);throw new Error('假別重新計算失敗，原工時紀錄已還原，請稍後再試。')}changed();return id},
    async deleteWorkRecord(record:Pick<WorkRecord,'id'|'workDate'>){if(!record.id)return false;if(!confirmDelete(`確定刪除 ${record.workDate} 的工時紀錄？刪除後無法復原。`))return false;const previous=await repository.getByDate(record.workDate);await repository.delete(record.id);try{await rebuild()}catch{if(previous)await repository.save(previous);throw new Error('假別重新計算失敗，原工時紀錄已還原，請稍後再試。')}changed();return true}
  }
}
