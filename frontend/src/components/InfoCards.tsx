import { useState, useEffect } from 'react'
import { useApp } from '../contexts/AppContext'
import { getRealtime, getFinancial, getIndicators } from '../api/stocks'

export default function InfoCards() {
  const { state } = useApp()
  const [realtime, setRealtime] = useState<any>(null)
  const [financial, setFinancial] = useState<any>(null)
  const [indicators, setIndicators] = useState<any>(null)

  useEffect(() => {
    if (!state.currentStock) return
    const code = state.currentStock.code
    Promise.all([
      getRealtime(code), getFinancial(code), getIndicators(code, 60)
    ]).then(([r, f, i]) => { setRealtime(r); setFinancial(f); setIndicators(i) })
  }, [state.currentStock])

  if (!realtime && !financial && !indicators) return null

  const macd = indicators?.data?.[indicators.data.length - 1]?.macd
  const rsi = indicators?.data?.[indicators.data.length - 1]?.rsi

  const items = [
    { label: '最新价', value: `¥${realtime?.price?.toFixed(2) || '--'}`, color: realtime?.change_pct > 0 ? 'var(--up)' : realtime?.change_pct < 0 ? 'var(--down)' : 'var(--heading)' },
    { label: '涨跌幅', value: realtime?.change_pct != null ? `${realtime.change_pct > 0 ? '+' : ''}${realtime.change_pct.toFixed(2)}%` : '--', color: realtime?.change_pct > 0 ? 'var(--up)' : realtime?.change_pct < 0 ? 'var(--down)' : 'var(--heading)' },
    { label: '最高', value: `¥${realtime?.high?.toFixed(2) || '--'}` },
    { label: '最低', value: `¥${realtime?.low?.toFixed(2) || '--'}` },
    { label: '成交量', value: realtime?.volume ? `${(realtime.volume / 10000).toFixed(0)}万` : '--' },
    { label: 'ROE', value: financial?.roe != null ? `${(financial.roe * 100).toFixed(1)}%` : '--' },
    { label: '负债率', value: financial?.debt_ratio != null ? `${(financial.debt_ratio * 100).toFixed(1)}%` : '--' },
    { label: 'MACD', value: macd?.macd != null ? macd.macd.toFixed(2) : '--', color: macd?.macd > 0 ? 'var(--up)' : 'var(--down)' },
    { label: 'RSI(14)', value: rsi?.toFixed ? rsi.toFixed(1) : '--' },
  ]

  return (
    <div className="info-cards">
      {items.map((item, i) => (
        <div key={i} className="info-card">
          <div className="label">{item.label}</div>
          <div className="value" style={item.color ? { color: item.color } : undefined}>{item.value}</div>
        </div>
      ))}
    </div>
  )
}
