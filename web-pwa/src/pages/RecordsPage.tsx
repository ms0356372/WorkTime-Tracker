import { useEffect,useState,type FormEvent } from 'react'
import { Card } from '../components/Card'
import type { ISODate,WorkRecord } from '../models/domain'
import { recordsRepository,settingsRepository } from '../repositories'
import { loadAnalysisSettings } from '../services/appDataService'
import { localISODate } from '../services/calendarService'
import { calculateWorkMinutes } from '../services/workTimeService'
import { formatMinutes } from '../utils/time'

export function RecordsPage({editDate,onEditLoaded}:{editDate?:string;onEditLoaded?:()=>void}={}){
  const today=localISODate(),[date,setDate]=useState<string>(today),[clockIn,setClockIn]=useState('08:00'),[clockOut,setClockOut]=useState('17:00'),[note,setNote]=useState(''),[recent,setRecent]=useState<WorkRecord[]>([]),[todayMinutes,setTodayMinutes]=useState(0),[message,setMessage]=useState(''),[editing,setEditing]=useState<WorkRecord>()
  async function refresh(){const rows=await recordsRepository.recent(5);setRecent(rows);const current=await recordsRepository.getByDate(today);setTodayMinutes(current?calculateWorkMinutes(current):0)}
  useEffect(()=>{void refresh()},[])
  useEffect(()=>{if(editDate)void recordsRepository.getByDate(editDate).then(record=>{if(record)edit(record);onEditLoaded?.()})},[editDate])
  function edit(record:WorkRecord){setEditing(record);setDate(record.workDate);setClockIn(record.clockIn??'');setClockOut(record.clockOut??'');setNote(record.note);setMessage('')}
  function cancel(){setEditing(undefined);setDate(today);setClockIn('08:00');setClockOut('17:00');setNote('');setMessage('')}
  async function save(event:FormEvent){event.preventDefault();try{const settings=await loadAnalysisSettings(today),breakStart=(await settingsRepository.get('lunch_break_start','12:00'))!,breakEnd=(await settingsRepository.get('lunch_break_end','13:00'))!,record:WorkRecord={id:editing?.id,workDate:(editing?.workDate??date) as ISODate,clockIn,clockOut,breakStart,breakEnd,deductBreak:true,standardMinutes:settings.dailyStandardMinutes,note:note.trim(),workdayType:'正常工作日',overnight:false};calculateWorkMinutes(record);await recordsRepository.save(record);setMessage(editing?'紀錄已更新。':'紀錄已儲存。');if(editing)cancel();else setNote('');await refresh()}catch(error){setMessage(error instanceof Error?error.message:'儲存失敗。')}}
  return <><div className="eyebrow">每日紀錄</div><h2 className="page-title">{editing?`編輯紀錄－${editing.workDate}`:'新增每日紀錄'}</h2><Card><form onSubmit={save}><div className="form-grid"><label>日期<input type="date" required disabled={!!editing} value={date} onChange={e=>setDate(e.target.value)}/></label><label>上班時間<input type="time" required value={clockIn} onChange={e=>setClockIn(e.target.value)}/></label><label>下班時間<input type="time" required value={clockOut} onChange={e=>setClockOut(e.target.value)}/></label><label className="wide">備註<input value={note} onChange={e=>setNote(e.target.value)} placeholder="選填"/></label></div><button type="submit">{editing?'儲存修改':'儲存紀錄'}</button>{editing&&<button type="button" className="secondary" onClick={cancel}>取消修改</button>}</form>{message&&<p className="notice">{message}</p>}</Card><Card title="今日工時"><strong>{formatMinutes(todayMinutes)}</strong></Card><Card title="最近紀錄"><div className="item-list calendar-list">{recent.map(row=><div className="list-row" key={row.workDate}><div><strong>{row.workDate} · {row.clockIn} - {row.clockOut}</strong><span>工時 {formatMinutes(calculateWorkMinutes(row))}</span></div><button className="small" onClick={()=>edit(row)}>修改</button>{row.id&&<button className="danger small" onClick={()=>void recordsRepository.delete(row.id!).then(refresh)}>刪除</button>}</div>)}{!recent.length&&<p className="empty">目前尚無工時紀錄。</p>}</div></Card></>
}
