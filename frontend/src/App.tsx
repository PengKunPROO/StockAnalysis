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
  const [tab, setTab] = useState('all')
  const filter = tab === 'all' ? state.watchlist : tab === 'sh' ? state.watchlist.filter(s => s.code?.startsWith('sh.')) : state.watchlist.filter(s => s.code?.startsWith('sz.'))
  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <span className="title">自选股</span>
        <span className="count">{state.watchlist.length}</span>
      </div>
      <div className="sidebar-tabs">
        {['all', 'sh', 'sz'].map(t => (
          <span key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>
            {t === 'all' ? '全部' : t === 'sh' ? '沪市' : '深市'}
          </span>
        ))}
      </div>
      <div className="sidebar-list">
        {filter.map(s => (
          <div key={s.code} className={`sidebar-item ${state.currentStock?.code === s.code ? 'selected' : ''}`}
            onClick={() => dispatch({ type: 'SET_STOCK', stock: { code: s.code, name: s.name, market: s.market, industry: '' } })}>
            <span className="name">{s.name}</span>
            <span className="code">{s.code?.replace('sh.', '').replace('sz.', '')}</span>
          </div>
        ))}
        {filter.length === 0 && <div style={{ padding: 20, textAlign: 'center', color: 'var(--muted)', fontSize: '0.75rem' }}>搜索股票添加</div>}
      </div>
      <div className="sidebar-footer">
        <button onClick={() => document.querySelector<HTMLInputElement>('.topbar .search-wrap input')?.focus()}>+ 添加自选</button>
      </div>
    </div>
  )
}

function TopBar() {
  const [indices, setIndices] = useState<{ name: string; price: number; change_pct: number }[]>([])
  const [themeOpen, setThemeOpen] = useState(false)
  const [theme, setTheme] = useState(() => localStorage.getItem('stock-theme') || 'dark')

  useEffect(() => {
    fetch('/api/v1/market/index?codes=sh.000001,sz.399001')
      .then(r => r.json()).then(d => setIndices((d.indices || []).map((i: any) => ({
        ...i, name: i.code?.startsWith('sh') ? '上证' : i.code?.startsWith('sz') ? '深证' : i.name || '--'
      }))))
      .catch(() => { })
  }, [])

  const switchTheme = (t: string) => {
    setTheme(t)
    localStorage.setItem('stock-theme', t)
    document.documentElement.setAttribute('data-theme', t)
    setThemeOpen(false)
  }

  return (
    <div className="topbar">
      <SearchBar />
      <div className="indices" style={{ position: 'relative' }}>
        {indices.map(idx => {
          const up = (idx.change_pct || 0) >= 0
          return <span key={idx.name}>{idx.name} <span className={up ? 'up' : 'down'}>{idx.price?.toFixed(2) || '--'}</span> {up ? '+' : ''}{idx.change_pct?.toFixed(2) || '--'}%</span>
        })}
      </div>
      <button className="theme-btn" onClick={() => setThemeOpen(!themeOpen)} title="切换主题">
        {theme === 'dark' ? '🌙 暗黑' : theme === 'eye' ? '🌿 护眼' : '⬛ 纯黑'}
      </button>
      {themeOpen && (
        <div className="theme-dropdown">
          <button className={theme === 'dark' ? 'active' : ''} onClick={() => switchTheme('dark')}>🌙 暗黑科技</button>
          <button className={theme === 'eye' ? 'active' : ''} onClick={() => switchTheme('eye')}>🌿 护眼绿豆沙</button>
          <button className={theme === 'black' ? 'active' : ''} onClick={() => switchTheme('black')}>⬛ 纯黑极简</button>
        </div>
      )}
    </div>
  )
}

function StatusBar() {
  return (
    <div className="statusbar">
      <span><span className="dot live" /> 数据就绪</span>
    </div>
  )
}

function AppShell() {
  const { state, dispatch } = useApp()
  const [skillOpen, setSkillOpen] = useState(false)
  const load = useCallback(async () => {
    try { dispatch({ type: 'SET_SKILLS', skills: await (await listSkills()).skills }) } catch {}
    try { dispatch({ type: 'SET_WATCHLIST', watchlist: await (await getWatchlist()).stocks }) } catch {}
  }, [dispatch])
  useEffect(() => { load() }, [load])

  return (
    <div className="app">
      <Sidebar />
      <div className="main">
        <TopBar />
        <div className="content">
          {state.currentStock ? <>
            <div className="stock-header">
              <span className="name">{state.currentStock.name}</span>
              <span className="code">{state.currentStock.code}</span>
            </div>
            <InfoCards />
            <KlineChart />
            <DiagnosisPanel onManageSkills={() => setSkillOpen(true)} />
          </> : (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', fontSize: '1rem', flexDirection: 'column', gap: 8 }}>
              <span style={{ fontSize: '2rem' }}>🔍</span>
              搜索股票代码或名称开始分析
              <span style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>支持 A股（sh.600519 / sz.000001）和美股（us.AAPL）</span>
            </div>
          )}
        </div>
        <StatusBar />
      </div>
      {state.currentStock && <NewsPanel />}
      {skillOpen && <SkillManager open={skillOpen} onClose={() => setSkillOpen(false)} onRefresh={load} />}
    </div>
  )
}

export default function App() { return <AppProvider><AppShell /></AppProvider> }
