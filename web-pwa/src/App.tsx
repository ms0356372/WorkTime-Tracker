import { useEffect,useState } from 'react'
import { BottomNavigation, type PageKey } from './components/BottomNavigation'
import { HomePage } from './pages/HomePage'
import { RecordsPage } from './pages/RecordsPage'
import { CalendarPage, type CalendarViewState } from './pages/CalendarPage'
import { AnalysisPage } from './pages/AnalysisPage'
import { SettingsPage } from './pages/SettingsPage'
import type { WorkRecord } from './models/domain'
import { DATA_RESTORED } from './services/backupService'
import { ledgerEvents } from './services/ledgerService'

export default function App() {
  const now=new Date(),[active,setActive]=useState<PageKey>('home'),[editDate,setEditDate]=useState<string>(),[editOrigin,setEditOrigin]=useState<CalendarViewState>(),[calendarView,setCalendarView]=useState<CalendarViewState>({year:now.getFullYear(),month:now.getMonth()+1}),[dataVersion,setDataVersion]=useState(0)
  useEffect(()=>{const refresh=()=>setDataVersion(x=>x+1);ledgerEvents.addEventListener(DATA_RESTORED,refresh);return()=>ledgerEvents.removeEventListener(DATA_RESTORED,refresh)},[])
  function edit(record:WorkRecord,origin:CalendarViewState){setEditDate(record.workDate);setEditOrigin(origin);setActive('records')}
  function editSaved(){if(!editOrigin)return;setCalendarView(editOrigin);setEditOrigin(undefined);setActive('calendar')}
  function navigate(page:PageKey){setEditDate(undefined);setEditOrigin(undefined);setActive(page)}
  let page
  if(active==='records')page=<RecordsPage editDate={editDate} onEditLoaded={()=>setEditDate(undefined)} onEditSaved={editOrigin?editSaved:undefined} onEditCancelled={()=>setEditOrigin(undefined)}/>
  else if(active==='calendar')page=<CalendarPage initialView={calendarView} onViewChange={view=>setCalendarView(view)} onScrollRestored={()=>setCalendarView(view=>({...view,scrollY:undefined}))} onEdit={edit}/>
  else if(active==='analysis')page=<AnalysisPage/>
  else if(active==='settings')page=<SettingsPage/>
  else page=<HomePage/>
  return <div className="app"><header><div><small>OFFLINE FIRST</small><h1>工時管家</h1></div><span className="status">PWA 0.1.0</span></header><main key={dataVersion}>{page}</main><BottomNavigation active={active} onChange={navigate}/></div>
}
