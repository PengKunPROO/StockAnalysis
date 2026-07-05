import { useEffect, useCallback, useState } from 'react'
import { AppProvider, useApp } from './contexts/AppContext'
import { listSkills } from './api/skills'
import { getWatchlist } from './api/watchlist'
import SearchBar from './components/SearchBar'
import KlineChart from './components/KlineChart'
import InfoCards from './components/InfoCards'
import DiagnosisPanel from './components/DiagnosisPanel'
import NewsPanel from './components/NewsPanel'
import SkillManager from './components/SkillManager'

function Sidebar() {
  const { state, dispatch } = useApp()
  return (
    <div className="sidebar">
      <div className="shd"><span>自选股</span><div className="dot"></div><span style={{marginLeft:'auto',fontSize:10,color:'var(--muted)'}}>{state.watchlist.length}</span></div>
      <div className="stabs"><span className="act">全部</span><span>沪</span><span>深</span></div>
      <div className="slist">
        {state.watchlist.map(s => (
          <div key={s.code} className={`sitem ${state.currentStock?.code===s.code?'sel':''}`}
            onClick={()=>dispatch({type:'SET_STOCK',stock:{code:s.code,name:s.name,market:s.market,industry:''}})}>
            <span className="nm">{s.name}</span><span className="cd">{s.code}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function TopBar() {
  const [indices, setIndices] = useState<{name:string;price:number;change_pct:number}[]>([])
  useEffect(() => {
    fetch('/api/v1/market/index?codes=sh.000001,sz.399001')
      .then(r=>r.json()).then(d=>setIndices((d.indices||[]).map((i:any)=>({...i,name:i.code?.startsWith('sh')?'上证':i.code?.startsWith('sz')?'深证':i.code||'--'}))))
      .catch(()=>{})
  }, [])
  return (
    <div className="topbar">
      <SearchBar />
      <div className="idx">
        {indices.map(idx=>{
          const up = idx.change_pct > 0
          return <span key={idx.name}>{idx.name} <span className={up?'up':'dn'}>{idx.price?.toFixed(2)||'--'}</span> {up?'+':''}{idx.change_pct?.toFixed(2)||'--'}%</span>
        })}
      </div>
    </div>
  )
}

function AppShell() {
  const { state, dispatch } = useApp()
  const [skillOpen, setSkillOpen] = useState(false)
  const load = useCallback(async () => {
    try { dispatch({type:'SET_SKILLS',skills:await (await listSkills()).skills}) } catch {}
    try { dispatch({type:'SET_WATCHLIST',watchlist:await (await getWatchlist()).stocks}) } catch {}
  }, [dispatch])
  useEffect(()=>{load()},[load])

  return (
    <div className="app">
      <Sidebar />
      <div className="main">
        <TopBar />
        <div className="content">
          <div className="center">
            {state.currentStock ? <>
              <div className="stkhd">
                <span className="nm">{state.currentStock.name}</span><span className="cd">{state.currentStock.code}</span>
              </div>
              <InfoCards />
              <KlineChart />
              <NewsPanel />
            </> : <div className="messages" style={{flex:1}}><div className="empty">搜索股票开始分析</div></div>}
          </div>
          <DiagnosisPanel onManageSkills={()=>setSkillOpen(true)} />
        </div>
      </div>
      {skillOpen && <SkillManager open={skillOpen} onClose={()=>setSkillOpen(false)} />}
    </div>
  )
}

export default function App() { return <AppProvider><AppShell/></AppProvider> }
