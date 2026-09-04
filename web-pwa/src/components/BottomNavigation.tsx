export type PageKey = 'home'|'records'|'calendar'|'analysis'|'settings'
const items: { key: PageKey; icon: string; label: string }[] = [
  {key:'home',icon:'⌂',label:'首頁'},{key:'records',icon:'＋',label:'紀錄'},{key:'calendar',icon:'▦',label:'日曆'},
  {key:'analysis',icon:'⌁',label:'分析'},{key:'settings',icon:'⚙',label:'設定'},
]
export function BottomNavigation({active,onChange}:{active:PageKey,onChange:(page:PageKey)=>void}) {
 return <nav className="bottom-nav" aria-label="主要導覽">{items.map(item=><button key={item.key} className={active===item.key?'active':''} aria-current={active===item.key?'page':undefined} onClick={()=>onChange(item.key)}><span>{item.icon}</span>{item.label}</button>)}</nav>
}
