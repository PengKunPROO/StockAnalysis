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

  const pct = realtime?.change_pct ?? 0
  const up = pct >= 0

  return (
    <div>
      <div className="price-header">
        <span style={{ color: '#888', fontSize: 14 }}>{stock.name}</span>
        <span style={{ color: '#555', fontSize: 12 }}>{stock.code}</span>
        <span className="price">{realtime?.price?.toFixed(2) || '--'}</span>
        <span className="change-pct" style={{ color: up ? '#22c55e' : '#ef4444' }}>
          {pct > 0 ? '+' : ''}{pct.toFixed(2)}%
        </span>
      </div>
      <div className="info-row">
        <div className="info-card"><div className="lbl">成交量</div><div className="val">{realtime?.volume ? (realtime.volume / 10000).toFixed(0) + '万' : '--'}</div></div>
        <div className="info-card"><div className="lbl">ROE</div><div className="val">{financial?.roe?.toFixed(1) || '--'}%</div></div>
        <div className="info-card"><div className="lbl">负债率</div><div className="val">{financial?.debt_ratio?.toFixed(1) || '--'}%</div></div>
        <div className="info-card"><div className="lbl">MACD</div>
          <div className="val" style={{ color: (indicators?.macd?.macd ?? 0) > 0 ? '#22c55e' : '#ef4444' }}>
            {indicators?.macd ? (indicators.macd.macd > 0 ? '金叉' : '死叉') + ' ' + indicators.macd.macd.toFixed(1) : '--'}
          </div>
        </div>
        <div className="info-card"><div className="lbl">RSI(14)</div>
          <div className="val" style={{ color: (indicators?.rsi?.rsi14 ?? 50) > 70 ? '#ef4444' : (indicators?.rsi?.rsi14 ?? 50) < 30 ? '#22c55e' : '#ddd' }}>
            {indicators?.rsi?.rsi14?.toFixed(0) || '--'}
          </div>
        </div>
        <div className="info-card"><div className="lbl">KDJ</div>
          <div className="val">
            {indicators?.kdj?.k != null ? `K${indicators.kdj.k.toFixed(0)} D${indicators.kdj.d.toFixed(0)}` : '--'}
          </div>
        </div>
        <div className="info-card"><div className="lbl">布林带</div>
          <div className="val">
            {indicators?.boll?.mid ? `${indicators.boll.mid.toFixed(0)}` : '--'}
          </div>
        </div>
      </div>
    </div>
  )
}
