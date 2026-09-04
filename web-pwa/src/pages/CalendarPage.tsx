import { useState } from 'react'
import { Card } from '../components/Card'
import { useWorkRecords } from '../hooks/useWorkRecords'
import { workRecordRepository } from '../repositories'
import { calculateWorkMinutes } from '../services/workTimeService'
import { nextMonth, previousMonth } from '../utils/date'
import { formatMinutes } from '../utils/time'
export function CalendarPage(){const now=new Date(),[value,setValue]=useState({year:now.getFullYear(),month:now.getMonth()+1});const {records,loading}=useWorkRecords(()=>workRecordRepository.recordsForMonth(value.year,value.month),[value.year,value.month]);return <><div className="eyebrow">月份紀錄</div><div className="month-switch"><button aria-label="上個月" onClick={()=>setValue(previousMonth(value))}>‹</button><h2>{value.year} 年 {value.month} 月</h2><button aria-label="下個月" onClick={()=>setValue(nextMonth(value))}>›</button></div><Card>{loading?<p className="empty">載入中…</p>:records.length===0?<p className="empty">此月份尚無工時紀錄。</p>:<div className="record-list">{records.map(record=><article key={record.id}><div><strong>{record.workDate.slice(5).replace('-','/')}</strong><span>{record.clockIn} - {record.clockOut}{record.overnight?'（跨日）':''}</span><span>工時 {formatMinutes(calculateWorkMinutes(record))}</span></div></article>)}</div>}</Card></>}
