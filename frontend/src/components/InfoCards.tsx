import { useState, useEffect, useRef } from 'react'
import { useApp } from '../contexts/AppContext'
import { getRealtime, getFinancial, getIndicators } from '../api/stocks'

export default function InfoCards() {
  const { state } = useApp()
  const [realtime, setRealtime] = useState<any>(null)
  const [financial, setFinancial] = useState<any>(null)
  const [indicators, setIndicators] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const latestRef = useRef('')

  useEffect(() => {
    const code = state.currentStock?.code
    if (!code) return
    latestRef.current = code
    setLoading(true)
    setRealtime(null); setFinancial(null); setIndicators(null)

    const load = async (forCode: string) => {
      try {
        const [r, f, i] = await Promise.all([
          getRealtime(code), getFinancial(code), getIndicators(code, 60),
        ])
        if (latestRef.current !== forCode) return
        setRealtime(r); setFinancial(f); setIndicators(i)
      } catch {}
      if (latestRef.current === forCode) setLoading(false)
    }
    load(code)
  }, [state.currentStock?.code])

  if (!state.currentStock) return null

  const roe = financial?.reports?.[0]?.roe ?? financial?.roe
  const debtRatio = financial?.reports?.[0]?.debt_ratio ?? financial?.debt_ratio
  const macd = indicators?.data?.[indicators.data.length - 1]?.macd
  const rsi = indicators?.data?.[indicators.data.length - 1]?.rsi
  const placeholder = loading ? '--' : '--'

  const items = [
    { label: '最新价', value: realtime?.price != null ? `¥${realtime.price.toFixed(2)}` : placeholder, color: realtime?.change_pct > 0 ? 'var(--up)' : realtime?.change_pct < 0 ? 'var(--down)' : undefined },
    { label: '涨跌幅', value: realtime?.change_pct != null ? `${realtime.change_pct > 0 ? '+' : ''}${realtime.change_pct.toFixed(2)}%` : placeholder, color: realtime?.change_pct > 0 ? 'var(--up)' : realtime?.change_pct < 0 ? 'var(--down)' : undefined },
    { label: '最高', value: realtime?.high != null ? `¥${realtime.high.toFixed(2)}` : placeholder },
    { label: '最低', value: realtime?.low != null ? `¥${realtime.low.toFixed(2)}` : placeholder },
    { label: '成交量', value: realtime?.volume != null ? `${(realtime.volume / 10000).toFixed(0)}万` : placeholder },
    { label: 'ROE', value: roe != null ? `${roe.toFixed(1)}%` : placeholder },
    { label: '负债率', value: debtRatio != null ? `${debtRatio.toFixed(1)}%` : placeholder },
    { label: 'MACD', value: macd?.macd != null ? macd.macd.toFixed(2) : placeholder, color: macd?.macd > 0 ? 'var(--up)' : 'var(--down)' },
    { label: 'RSI(14)', value: rsi?.toFixed ? rsi.toFixed(1) : placeholder },
  ]

  return (
    <div className="info-cards" style={{ opacity: loading ? 0.6 : 1, transition: 'opacity .2s' }}>
      {items.map((item, i) => (
        <div key={i} className="info-card">
          <div className="label">{item.label}</div>
          <div className="value" style={item.color ? { color: item.color } : undefined}>{item.value}</div>
        </div>
      ))}
    </div>
  )
}
