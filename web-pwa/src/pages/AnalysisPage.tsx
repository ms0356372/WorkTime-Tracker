import { Card } from '../components/Card'
const metrics=['總工時','出勤天數','平均每日工時','超時','不足','假日工作']
export function AnalysisPage(){return <><div className="eyebrow">趨勢與餘額</div><h2 className="page-title">月份分析</h2><div className="metric-grid">{metrics.map(x=><Card key={x}><span>{x}</span><strong>{x==='出勤天數'?'0 天':'0 小時 0 分'}</strong></Card>)}</div><Card title="年度摘要"><p>年度總工時　<strong>0 小時 0 分</strong></p><p>年度出勤天數　<strong>0 天</strong></p></Card><Card title="假別 / 補休"><p className="empty">Ledger 與分析移植後顯示可靠餘額</p></Card></>}
