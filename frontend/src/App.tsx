import { useEffect, useCallback } from 'react'
import { AppProvider, useApp } from './contexts/AppContext'
import { listSkills } from './api/skills'
import { getWatchlist } from './api/watchlist'
import SearchBar from './components/SearchBar'
import KlineChart from './components/KlineChart'
import InfoCards from './components/InfoCards'
import DiagnosisPanel from './components/DiagnosisPanel'
import NewsPanel from './components/NewsPanel'
import SkillManager from './components/SkillManager'

function IconBar() {
  const { state, dispatch } = useApp()
  return (
    <div className="iconbar">
      <div className="icon" title="自选股">📊</div>
      <div className="watchlist-popup">
        {state.watchlist.map(s => (
          <div key={s.code} className={`item ${state.currentStock?.code === s.code ? 'active' : ''}`}
            onClick={() => dispatch({ type: 'SET_STOCK', stock: { code: s.code, name: s.name, market: s.market, industry: '' } })}>
            <span>{s.name}</span><span style={{ color: 'var(--muted)', fontSize: 10 }}>{s.code}</span>
          </div>
        ))}
        {state.watchlist.length === 0 && <div style={{ padding: '8px 12px', fontSize: 11, color: 'var(--muted)' }}>搜索股票添加</div>}
      </div>
    </div>
  )
}

function AppShell() {
  const { state, dispatch } = useApp()
  const refreshSkills = useCallback(() => {
    listSkills().then(d => dispatch({ type: 'SET_SKILLS', skills: d.skills }))
  }, [dispatch])

  useEffect(() => {
    refreshSkills()
    getWatchlist().then(d => dispatch({ type: 'SET_WATCHLIST', watchlist: d.stocks }))
  }, [refreshSkills])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      <div className="topbar">
        <span className="logo">◆ Stock Agent</span>
        <SearchBar />
        <button onClick={() => dispatch({ type: 'TOGGLE_SKILL_MANAGER' })} title="Skill管理">⚙ Skill</button>
      </div>
      <div className="main">
        <IconBar />
        <div className="content">
          {state.currentStock ? <><InfoCards /><KlineChart /><NewsPanel /></> : <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', fontSize: 16 }}>搜索股票开始分析</div>}
        </div>
        <DiagnosisPanel />
      </div>
      <SkillManager open={state.skillManagerOpen} onClose={() => dispatch({ type: 'TOGGLE_SKILL_MANAGER', open: false })} onRefresh={refreshSkills} />
    </div>
  )
}

export default function App() { return <AppProvider><AppShell /></AppProvider> }
