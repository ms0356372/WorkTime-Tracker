import { Card } from '../components/Card'
import { useWorkRecords } from '../hooks/useWorkRecords'
import { workRecordRepository } from '../repositories'
import { summarize } from '../services/analysisService'
import { calculateWorkMinutes } from '../services/workTimeService'
import { localISODate } from '../utils/date'
import { formatMinutes } from '../utils/time'
export function HomePage(){const today=localISODate(),now=new Date();const {records}=useWorkRecords(()=>workRecordRepository.recordsForMonth(now.getFullYear(),now.getMonth()+1),[]);const todayRecord=records.find(record=>record.workDate===today);return <><div className="eyebrow">今日摘要</div><h2 className="page-title">掌握每一分鐘</h2><div className="metric-grid"><Card><span>今天工時</span><strong>{formatMinutes(todayRecord?calculateWorkMinutes(todayRecord):0)}</strong></Card><Card><span>本月工時</span><strong>{formatMinutes(summarize(records).workMinutes)}</strong></Card></div><Card title="補休與特休"><p className="empty">餘額將於後續 Ledger Phase 提供；目前不顯示推估值。</p></Card><Card title="匯出資料"><p className="empty">Excel 匯出將於後續 Phase 提供。</p></Card></>}
