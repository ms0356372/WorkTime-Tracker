import { useEffect,useState } from 'react'
import { Card } from '../components/Card'
import { recordsRepository } from '../repositories'
import { summarizeMonth,type Summary } from '../services/analysisService'
import { loadAnalysisSettings,loadCalendar } from '../services/appDataService'
import { localISODate } from '../services/calendarService'
import { WORK_RECORDS_CHANGED,workRecordEvents } from '../services/workRecordMutations'
import { calculateWorkMinutes } from '../services/workTimeService'
import { formatMinutes } from '../utils/time'

const blank:Summary={workMinutes:0,attendanceDays:0,averageMinutes:0,overtimeMinutes:0,shortfallMinutes:0,holidayWorkMinutes:0,scheduledWorkdays:0,missingWorkdays:0}
export async function loadHomeSummary(today=localISODate()){
  const year=Number(today.slice(0,4)),month=Number(today.slice(5,7))
  const [records,todayRecord,calendar,settings]=await Promise.all([recordsRepository.recordsForMonth(year,month),recordsRepository.getByDate(today),loadCalendar([year]),loadAnalysisSettings(today)])
  return {todayMinutes:todayRecord?calculateWorkMinutes(todayRecord):0,month:summarizeMonth(records,calendar,{year,month,...settings,calculationStartDate:settings.calculationStartDate as `${number}-${number}-${number}`,today})}
}
export function HomePage(){
  const [data,setData]=useState(blank),[todayMinutes,setTodayMinutes]=useState(0),[error,setError]=useState('')
  useEffect(()=>{const refresh=()=>{void loadHomeSummary().then(result=>{setTodayMinutes(result.todayMinutes);setData(result.month);setError('')}).catch(()=>setError('摘要載入失敗，請稍後再試。'))};refresh();workRecordEvents.addEventListener(WORK_RECORDS_CHANGED,refresh);return()=>workRecordEvents.removeEventListener(WORK_RECORDS_CHANGED,refresh)},[])
  return <><div className="eyebrow">本月摘要</div><h2 className="page-title">掌握每一分鐘</h2>{error&&<p className="notice" role="alert">{error}</p>}<div className="metric-grid"><Card><span>今日工時</span><strong>{formatMinutes(todayMinutes)}</strong></Card><Card><span>本月工時</span><strong>{formatMinutes(data.workMinutes)}</strong></Card><Card><span>本月出勤</span><strong>{data.attendanceDays} 天</strong></Card><Card><span>本月超時</span><strong>{formatMinutes(data.overtimeMinutes)}</strong></Card><Card><span>本月不足</span><strong>{formatMinutes(data.shortfallMinutes)}</strong></Card></div><Card title="後續階段"><p className="empty">補休、月補休、年度補休、特休與 Ledger 餘額尚未提供；此處不顯示推測數值。</p></Card></>
}
