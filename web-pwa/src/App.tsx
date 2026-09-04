import { useState } from 'react'
import { BottomNavigation, type PageKey } from './components/BottomNavigation'
import { HomePage } from './pages/HomePage'
import { RecordsPage } from './pages/RecordsPage'
import { CalendarPage } from './pages/CalendarPage'
import { AnalysisPage } from './pages/AnalysisPage'
import { SettingsPage } from './pages/SettingsPage'

const pages = { home: HomePage, records: RecordsPage, calendar: CalendarPage, analysis: AnalysisPage, settings: SettingsPage }
export default function App() {
  const [active, setActive] = useState<PageKey>('home')
  const Page = pages[active]
  return <div className="app"><header><div><small>OFFLINE FIRST</small><h1>工時管家</h1></div><span className="status">PWA 0.1.0</span></header><main><Page /></main><BottomNavigation active={active} onChange={setActive}/></div>
}
