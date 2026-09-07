import { useEffect,useState } from 'react'
import { Card } from '../components/Card'
import type { WorkRecord } from '../models/domain'
import { recordsRepository,workRecordMutations } from '../repositories'
import { nextMonth,previousMonth } from '../utils/date'
import { calculateWorkMinutes } from '../services/workTimeService'
import { formatMinutes } from '../utils/time'
export function CalendarPage({onEdit}:{onEdit:(record:WorkRecord)=>void}){
  const now=new Date(),[value,setValue]=useState({year:now.getFullYear(),month:now.getMonth()+1}),[rows,setRows]=useState<WorkRecord[]>([]),[message,setMessage]=useState('')
  async function refresh(){try{setRows(await recordsRepository.recordsForMonth(value.year,value.month))}catch{setMessage('月份紀錄載入失敗，請稍後再試。')}}
  async function remove(row:WorkRecord){try{if(await workRecordMutations.deleteWorkRecord(row)){setMessage(`${row.workDate} 的紀錄已刪除。`);await refresh()}}catch{setMessage('刪除失敗，原紀錄仍保留。')}}
  useEffect(()=>{void refresh()},[value])
  return <><div className="eyebrow">月份紀錄</div><div className="month-switch"><button aria-label="上個月" onClick={()=>setValue(previousMonth(value))}>‹</button><h2>{value.year} 年 {value.month} 月</h2><button aria-label="下個月" onClick={()=>setValue(nextMonth(value))}>›</button></div>{message&&<p className="notice" role="status">{message}</p>}<Card title="月份紀錄"><div className="item-list calendar-list">{rows.map(row=><div className="list-row" key={row.workDate}><div><strong>{row.workDate.slice(5).replace('-','/')}</strong><span>{row.clockIn} - {row.clockOut} · 工時 {formatMinutes(calculateWorkMinutes(row))}</span></div><div className="row-actions"><button className="small" onClick={()=>onEdit(row)}>修改</button>{row.id&&<button className="danger small" onClick={()=>void remove(row)}>刪除</button>}</div></div>)}{!rows.length&&<p className="empty">此月份尚無工時紀錄</p>}</div></Card></>
}
