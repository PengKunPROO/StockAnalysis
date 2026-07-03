import { useState, useEffect } from 'react'
import { useApp } from '../contexts/AppContext'
import { getRealtime, getFinancial, getIndicators } from '../api/stocks'
import type { IndicatorPoint } from '../types'

export default function InfoCards() {
  const { state } = useApp()
  const stock = state.currentStock
  const [realtime, setRealtime] = useState<any>(null)
  const [financial, setFinancial] = useState<any>(null)
  const [indicators, setIndicators] = useState<IndicatorPoint | null>(null)

  useEffect(() => {
    if (!stock) return
    getRealtime(stock.code).then(setRealtime).catch(() => {})
    getFinancial(stock.code).then(d => setFinancial(d.reports?.[0])).catch(() => {})
    getIndicators(stock.code, 60).then(d => setIndicators(d.data?.[d.data.length - 1] || null))
  }, [stock])

  if (!stock) return null

  const pct = realtime?.change_pct ?? 0; const up = pct >= 0
  const cards = [
    { label: '最新价', value: realtime?.price?.toFixed(2) || '--', color: 'var(--text)' },
    { label: '涨跌幅', value: `${pct > 0 ? '+' : ''}${pct.toFixed(2)}%`, color: up ? 'var(--up)' : 'var(--down)' },
    { label: '成交量', value: realtime?.volume ? `${(realtime.volume / 10000).toFixed(0)}万` : '--' },
    { label: 'ROE', value: financial?.roe != null ? `${financial.roe.toFixed(1)}%` : '--' },
    { label: '负债率', value: financial?.debt_ratio != null ? `${financial.debt_ratio.toFixed(1)}%` : '--' },
    { label: 'MACD', value: indicators?.macd ? `${indicators.macd.macd > 0 ? '金叉' : '死叉'} ${indicators.macd.macd.toFixed(1)}` : '--', color: (indicators?.macd?.macd ?? 0) > 0 ? 'var(--up)' : 'var(--down)' },
    { label: 'RSI(14)', value: indicators?.rsi?.rsi14?.toFixed(0) || '--' },
    { label: 'KDJ', value: indicators?.kdj?.k != null ? `K${indicators.kdj.k.toFixed(0)} D${indicators.kdj.d.toFixed(0)}` : '--' },
  ]

  return (
    <div>
      <div className="price-header">
        <span className="name">{stock.name}</span>
        <span className="code">{stock.code}</span>
        <span className="price" style={{ color: up ? 'var(--up)' : 'var(--down)' }}>{realtime?.price?.toFixed(2) || '--'}</span>
        <span className="change" style={{ color: up ? 'var(--up)' : 'var(--down)' }}>{pct > 0 ? '+' : ''}{pct.toFixed(2)}%</span>
      </div>
      <div className="info-row">
        {cards.map(c => (
          <div key={c.label} className="info-card">
            <div className="lbl">{c.label}</div>
            <div className="val" style={{ color: c.color || undefined }}>{c.value}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
