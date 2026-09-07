import { useEffect,useState } from 'react'
import { BottomNavigation, type PageKey } from './components/BottomNavigation'
import { HomePage } from './pages/HomePage'
import { RecordsPage } from './pages/RecordsPage'
import { CalendarPage } from './pages/CalendarPage'
import { AnalysisPage } from './pages/AnalysisPage'
import { SettingsPage } from './pages/SettingsPage'
import type { WorkRecord } from './models/domain'
import { DATA_RESTORED } from './services/backupService'
import { ledgerEvents } from './services/ledgerService'

export default function App() {
  const [active,setActive]=useState<PageKey>('home'),[editDate,setEditDate]=useState<string>(),[dataVersion,setDataVersion]=useState(0)
  useEffect(()=>{const refresh=()=>setDataVersion(x=>x+1);ledgerEvents.addEventListener(DATA_RESTORED,refresh);return()=>ledgerEvents.removeEventListener(DATA_RESTORED,refresh)},[])
  function edit(record:WorkRecord){setEditDate(record.workDate);setActive('records')}
  let page
  if(active==='records')page=<RecordsPage editDate={editDate} onEditLoaded={()=>setEditDate(undefined)}/>
  else if(active==='calendar')page=<CalendarPage onEdit={edit}/>
  else if(active==='analysis')page=<AnalysisPage/>
  else if(active==='settings')page=<SettingsPage/>
  else page=<HomePage/>
  return <div className="app"><header><div><small>OFFLINE FIRST</small><h1>工時管家</h1></div><span className="status">PWA 0.1.0</span></header><main key={dataVersion}>{page}</main><BottomNavigation active={active} onChange={setActive}/></div>
}
