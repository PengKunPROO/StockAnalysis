import { useApp, type AppView } from '../contexts/AppContext'

const TABS: { key: AppView; label: string; icon: string }[] = [
  { key: 'stock', label: '个股分析', icon: '📈' },
  { key: 'screener', label: '选股器', icon: '🔍' },
  { key: 'intel', label: '市场情报', icon: '🌐' },
]

export default function TopTabBar() {
  const { state, dispatch } = useApp()
  return (
    <div className="top-tab-bar">
      {TABS.map(t => (
        <button
          key={t.key}
          className={`top-tab ${state.activeView === t.key ? 'active' : ''}`}
          onClick={() => dispatch({ type: 'SET_VIEW', view: t.key })}
        >
          <span className="icon">{t.icon}</span>
          <span className="label">{t.label}</span>
        </button>
      ))}
    </div>
  )
}
