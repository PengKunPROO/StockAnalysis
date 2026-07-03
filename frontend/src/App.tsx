import { useEffect, useCallback, useState } from 'react'
import { AppProvider, useApp } from './contexts/AppContext'
import { listSkills } from './api/skills'
import { getWatchlist } from './api/watchlist'
import SearchBar from './components/SearchBar'
import KlineChart from './components/KlineChart'
import InfoCards from './components/InfoCards'
import DiagnosisPanel from './components/DiagnosisPanel'
import SkillManager from './components/SkillManager'
import { Sheet, SheetContent, SheetTrigger } from "./components/ui/sheet"
import { Button } from "./components/ui/button"
import { Separator } from "./components/ui/separator"
import { Menu, Settings } from 'lucide-react'

function Sidebar() {
  const { state, dispatch } = useApp()
  return (
    <div className="flex flex-col h-full bg-sidebar">
      <div className="px-4 py-3 text-xs text-muted uppercase tracking-wider font-semibold">自选股</div>
      {state.watchlist.map(s => (
        <div
          key={s.code}
          onClick={() => dispatch({ type: 'SET_STOCK', stock: { code: s.code, name: s.name, market: s.market, industry: '' } })}
          className={`px-4 py-2 cursor-pointer text-sm border-b border-border hover:bg-gray-100 transition-colors ${state.currentStock?.code === s.code ? 'bg-blue-50 border-l-[3px] border-l-accent font-semibold' : ''}`}
        >
          {s.name}
          <span className="text-xs text-muted ml-2">{s.code}</span>
        </div>
      ))}
      {state.watchlist.length === 0 && (
        <div className="px-4 py-3 text-sm text-muted">搜索股票添加</div>
      )}
    </div>
  )
}

function AppShell() {
  const { state, dispatch } = useApp()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const refreshSkills = useCallback(() => {
    listSkills().then(d => dispatch({ type: 'SET_SKILLS', skills: d.skills }))
  }, [dispatch])

  useEffect(() => {
    refreshSkills()
    getWatchlist().then(d => dispatch({ type: 'SET_WATCHLIST', watchlist: d.stocks }))
  }, [refreshSkills])

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-2 bg-surface border-b border-border flex-shrink-0">
        <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" title="自选股列表"><Menu className="h-5 w-5" /></Button>
          </SheetTrigger>
          <SheetContent side="left" className="p-0 w-[240px]">
            <Sidebar />
          </SheetContent>
        </Sheet>
        <span className="font-bold text-lg text-accent whitespace-nowrap">Stock Agent</span>
        <SearchBar />
        <Button variant="outline" size="sm" onClick={() => dispatch({ type: 'TOGGLE_SKILL_MANAGER' })} title="管理分析 Skill">
          <Settings className="h-4 w-4 mr-1" /> Skill
        </Button>
      </div>

      <div className="flex-1 overflow-hidden">
        {state.currentStock ? (
          <div className="flex flex-col h-full">
            <div className="flex-shrink-0">
              <InfoCards />
              <KlineChart />
              <Separator />
            </div>
            <DiagnosisPanel />
          </div>
        ) : (
          <div className="flex-1 flex flex-col"><DiagnosisPanel /></div>
        )}
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
  return <AppProvider><AppShell /></AppProvider>
}
