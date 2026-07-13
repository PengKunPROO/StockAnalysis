// frontend/src/components/PortfolioDashboard.tsx
import type { Holding } from '../api/portfolio'

interface DashboardProps {
  holdings: Holding[]
  totalMarketValue: number
  totalCost: number
  totalPnl: number
  pnlPct: number
  todayChange: number
  todayChangePct: number
}

const DONUT_COLORS = ['var(--accent)', 'var(--up)', 'var(--gold)', 'var(--down)', 'var(--muted)']

export default function PortfolioDashboard({
  holdings, totalMarketValue, totalCost, totalPnl, pnlPct, todayChange, todayChangePct,
}: DashboardProps) {
  const isPnlUp = totalPnl >= 0
  const isTodayUp = todayChange >= 0
  const count = holdings.length

  // Position distribution for donut
  const weights = holdings.map(h => h.shares * h.avg_cost)
  const totalWeight = weights.reduce((a, b) => a + b, 0) || 1
  const top5 = holdings.slice(0, 5)
  const weightPcts = top5.map(h => {
    const w = h.shares * h.avg_cost
    return Math.round((w / totalWeight) * 100)
  })

  // Build conic-gradient segments
  let acc = 0
  const segments = top5.map((_, i) => {
    const pct = weightPcts[i]
    const start = acc
    acc += pct
    const end = acc
    return `${DONUT_COLORS[i % DONUT_COLORS.length]} ${start * 3.6}deg ${end * 3.6}deg`
  }).join(', ')

  const donutStyle: React.CSSProperties = {
    background: `conic-gradient(${segments})`,
  }

  const fmt = (v: number) => {
    if (Math.abs(v) >= 10000) return `¥${(v / 10000).toFixed(2)}万`
    return `¥${v.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`
  }

  const shortName = (name: string) => name.length > 4 ? name.slice(0, 4) : name

  return (
    <div className="pf-dashboard">
      <div className="pf-card">
        <span className="label">总市值</span>
        <span className="value">{fmt(totalMarketValue)}</span>
        <span className={`sub ${isTodayUp ? 'up' : 'down'}`}>
          {isTodayUp ? '+' : ''}{fmt(Math.abs(todayChange))} ({isTodayUp ? '+' : ''}{todayChangePct.toFixed(2)}%)
        </span>
      </div>
      <div className="pf-card">
        <span className="label">总成本</span>
        <span className="value">{fmt(totalCost)}</span>
        <span className="sub" style={{ color: 'var(--muted)' }}>{count}只持仓</span>
      </div>
      <div className="pf-card">
        <span className="label">总盈亏</span>
        <span className="value" style={{ color: isPnlUp ? 'var(--up)' : 'var(--down)' }}>
          {isPnlUp ? '+' : ''}{fmt(Math.abs(totalPnl))}
        </span>
        <span className={`sub ${isPnlUp ? 'up' : 'down'}`}>
          {isPnlUp ? '+' : ''}{pnlPct.toFixed(2)}%
        </span>
      </div>
      <div className="pf-card">
        <span className="label">今日变动</span>
        <span className="value" style={{ color: isTodayUp ? 'var(--up)' : 'var(--down)' }}>
          {isTodayUp ? '+' : ''}{fmt(Math.abs(todayChange))}
        </span>
        <span className={`sub ${isTodayUp ? 'up' : 'down'}`}>
          {isTodayUp ? '+' : ''}{todayChangePct.toFixed(2)}%
        </span>
      </div>
      <div className="pf-card distribution">
        <span className="label">仓位分布</span>
        <div className="donut-wrap">
          <div className="donut" style={donutStyle} />
          <div className="donut-legend">
            {top5.map((h, i) => (
              <div className="item" key={h.code}>
                <span className={`dot c${i + 1}`} style={i >= 4 ? { background: 'var(--muted)' } : undefined} />
                {shortName(h.name)} <span className="pct">{weightPcts[i]}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
