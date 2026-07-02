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

function StockDetail() {
  const { state } = useApp()
  if (!state.currentStock) return <div className="placeholder">搜索股票开始分析</div>
  return (
    <div className="detail">
      <div className="chart-section">
        <KlineChart />
        <InfoCards />
      </div>
      <div className="diagnosis-section">
        <DiagnosisPanel />
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
    <div className="app">
      <SearchBar />
      <StockDetail />
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
