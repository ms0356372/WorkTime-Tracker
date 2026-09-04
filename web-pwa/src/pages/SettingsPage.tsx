import { Card } from '../components/Card'
const sections=[['基本工時','每日標準工時、工時計算起始日與扣除順序'],['特休','年度核給、結算日與年度摘要'],['補休','月／年結算、累計上限、折現與月結紀錄'],['午休','依上班區間重疊分鐘扣除'],['工作日曆','平日、國定假日與更新狀態'],['特殊日期','公司補班／休假覆寫'],['假別轉換','補休與特休轉換、撤銷紀錄'],['資料管理','JSON 備份、Android 匯入與還原']]
export function SettingsPage(){return <><div className="eyebrow">個人化規則</div><h2 className="page-title">設定</h2>{sections.map(([title,text])=><Card title={title} key={title}><p>{text}</p><span className="badge">規劃完成 · 尚未實作</span></Card>)}</>}
