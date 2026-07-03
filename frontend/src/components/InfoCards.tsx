import { useState, useEffect } from 'react'
import { Card } from '@/components/ui/card'
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

  const pct = realtime?.change_pct ?? 0
  const up = pct >= 0
  const cards = [
    { label: '最新价', value: realtime?.price?.toFixed(2) || '--', color: up ? 'text-up' : 'text-down' },
    { label: '涨跌幅', value: `${pct > 0 ? '+' : ''}${pct.toFixed(2)}%`, color: up ? 'text-up' : 'text-down' },
    { label: '成交量', value: realtime?.volume ? `${(realtime.volume / 10000).toFixed(0)}万` : '--' },
    { label: 'ROE', value: financial?.roe != null ? `${financial.roe.toFixed(1)}%` : '--' },
    { label: '负债率', value: financial?.debt_ratio != null ? `${financial.debt_ratio.toFixed(1)}%` : '--' },
    { label: 'MACD', value: indicators?.macd ? `${indicators.macd.macd > 0 ? '金叉' : '死叉'} ${indicators.macd.macd.toFixed(1)}` : '--', color: (indicators?.macd?.macd ?? 0) > 0 ? 'text-up' : 'text-down' },
    { label: 'RSI(14)', value: indicators?.rsi?.rsi14?.toFixed(0) || '--', color: (indicators?.rsi?.rsi14 ?? 50) > 70 ? 'text-down' : (indicators?.rsi?.rsi14 ?? 50) < 30 ? 'text-up' : '' },
    { label: 'KDJ', value: indicators?.kdj?.k != null ? `K${indicators.kdj.k.toFixed(0)} D${indicators.kdj.d.toFixed(0)}` : '--' },
  ]

  return (
    <div>
      <div className="flex items-baseline gap-4 px-5 py-3 bg-surface">
        <span className="text-muted text-sm">{stock.name}</span>
        <span className="text-xs text-muted">{stock.code}</span>
        <span className="text-2xl font-bold">{realtime?.price?.toFixed(2) || '--'}</span>
        <span className={`text-base font-semibold ${up ? 'text-up' : 'text-down'}`}>
          {pct > 0 ? '+' : ''}{pct.toFixed(2)}%
        </span>
      </div>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(100px,1fr))] gap-2 px-4 pb-3">
        {cards.map(c => (
          <Card key={c.label} className="p-2.5 text-center shadow-none border border-border/50">
            <div className="text-[10px] text-muted whitespace-nowrap">{c.label}</div>
            <div className={`text-sm font-semibold ${c.color || ''}`}>{c.value}</div>
          </Card>
        ))}
      </div>
    </div>
  )
}
