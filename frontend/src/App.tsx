import { useEffect, useCallback } from 'react'
import { AppProvider, useApp } from './contexts/AppContext'
import { listSkills } from './api/skills'
import { getWatchlist } from './api/watchlist'
import SearchBar from './components/SearchBar'
import KlineChart from './components/KlineChart'
import InfoCards from './components/InfoCards'
import DiagnosisPanel from './components/DiagnosisPanel'
import SkillManager from './components/SkillManager'
import './App.css'

function Sidebar() {
  const { state, dispatch } = useApp()
  return (
    <div className="sidebar">
      <h3>持仓 / 自选</h3>
      {state.watchlist.map(s => (
        <div
          key={s.code}
          className={`stock-item ${state.currentStock?.code === s.code ? 'active' : ''}`}
          onClick={() => dispatch({ type: 'SET_STOCK', stock: { code: s.code, name: s.name, market: s.market, industry: '' } })}
        >
          <span>{s.name}</span>
        </div>
      ))}
      {state.watchlist.length === 0 && (
        <div style={{ color: '#555', padding: '8px 14px', fontSize: 12 }}>搜索股票添加</div>
      )}
    </div>
  )
}

function StockView() {
  const { state, dispatch } = useApp()
  if (!state.currentStock) {
    return (
      <div className="content">
        <div className="chat-area">
          <div className="empty">搜索一只股票开始分析</div>
        </div>
        <DiagnosisPanel />
      </div>
    )
  }

  return (
    <div className="content">
      <div className="chart-area">
        <InfoCards />
        <KlineChart />
      </div>
      <DiagnosisPanel />
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
    <div className="app">
      <div className="topbar">
        <span className="title">📈 Stock Agent</span>
        <div className="search-wrap">
          <SearchBar />
        </div>
        <button
          onClick={() => dispatch({ type: 'TOGGLE_SKILL_MANAGER' })}
          className="btn-secondary"
          style={{
            background: '#1a1a35', color: '#ccc', border: '1px solid #3a3a50',
            borderRadius: 6, padding: '6px 12px', cursor: 'pointer', fontSize: 12,
          }}
          title="管理分析 Skill"
        >⚙ Skill</button>
      </div>
      <div className="main">
        <Sidebar />
        <StockView />
      </div>
      <SkillManager
        open={state.skillManagerOpen}
        onClose={() => dispatch({ type: 'TOGGLE_SKILL_MANAGER', open: false })}
        onRefresh={refreshSkills}
      />
    </div>
  )
}

export default function App() {
  return (
    <AppProvider>
      <AppShell />
    </AppProvider>
  )
}
