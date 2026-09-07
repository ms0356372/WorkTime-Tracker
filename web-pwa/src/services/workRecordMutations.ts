import type { WorkRecordRepository } from '../repositories/contracts'
import type { WorkRecord } from '../models/domain'

export const WORK_RECORDS_CHANGED='work-records-changed'
export const workRecordEvents=new EventTarget()
export interface MutationOptions{events?:EventTarget;confirmDelete?:(message:string)=>boolean}
export function createWorkRecordMutations(repository:WorkRecordRepository,options:MutationOptions={}){
  const events=options.events??workRecordEvents,confirmDelete=options.confirmDelete??((message:string)=>window.confirm(message))
  const changed=()=>events.dispatchEvent(new Event(WORK_RECORDS_CHANGED))
  return {
    async saveWorkRecord(record:WorkRecord){const id=await repository.save(record);changed();return id},
    async deleteWorkRecord(record:Pick<WorkRecord,'id'|'workDate'>){if(!record.id)return false;if(!confirmDelete(`確定刪除 ${record.workDate} 的工時紀錄？刪除後無法復原。`))return false;await repository.delete(record.id);changed();return true}
  }
}
