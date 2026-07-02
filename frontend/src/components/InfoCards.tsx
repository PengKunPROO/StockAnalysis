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

  const card = { background: '#222', borderRadius: 8, padding: 12, marginBottom: 8 }
  const changeColor = (realtime?.change_pct || 0) >= 0 ? '#26a69a' : '#ef5350'

  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ display: 'flex', gap: 8 }}>
        <div style={{ ...card, flex: 1 }}>
          <div style={{ color: '#888', fontSize: 12 }}>最新价</div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>
            {realtime?.price?.toFixed(2) || '--'}
          </div>
          <div style={{ color: changeColor }}>
            {realtime?.change_pct != null ? `${realtime.change_pct > 0 ? '+' : ''}${realtime.change_pct.toFixed(2)}%` : '--'}
          </div>
        </div>
        <div style={{ ...card, flex: 1 }}>
          <div style={{ color: '#888', fontSize: 12 }}>PE / PB</div>
          <div style={{ fontSize: 16 }}>
            {financial?.pe_ratio?.toFixed(1) || '--'} / {financial?.pb_ratio?.toFixed(1) || '--'}
          </div>
        </div>
        <div style={{ ...card, flex: 1 }}>
          <div style={{ color: '#888', fontSize: 12 }}>ROE</div>
          <div style={{ fontSize: 16 }}>{financial?.roe?.toFixed(1) || '--'}%</div>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <div style={{ ...card, flex: 1 }}>
          <div style={{ color: '#888', fontSize: 12 }}>MACD</div>
          <div style={{ fontSize: 14 }}>
            {indicators?.macd ? (
              <span style={{ color: indicators.macd.macd > 0 ? '#26a69a' : '#ef5350' }}>
                {indicators.macd.macd > 0 ? '金叉' : '死叉'} {indicators.macd.macd.toFixed(2)}
              </span>
            ) : '--'}
          </div>
        </div>
        <div style={{ ...card, flex: 1 }}>
          <div style={{ color: '#888', fontSize: 12 }}>RSI(14)</div>
          <div style={{ fontSize: 14 }}>
            {indicators?.rsi?.rsi14 != null ? (
              <span style={{ color: indicators.rsi.rsi14 > 70 ? '#ef5350' : indicators.rsi.rsi14 < 30 ? '#26a69a' : '#ddd' }}>
                {indicators.rsi.rsi14}
                {indicators.rsi.rsi14 > 70 ? ' 超买' : indicators.rsi.rsi14 < 30 ? ' 超卖' : ''}
              </span>
            ) : '--'}
          </div>
        </div>
        <div style={{ ...card, flex: 1 }}>
          <div style={{ color: '#888', fontSize: 12 }}>KDJ</div>
          <div style={{ fontSize: 14 }}>
            {indicators?.kdj?.k != null
              ? `K${indicators.kdj.k.toFixed(0)} D${indicators.kdj.d.toFixed(0)} J${indicators.kdj.j.toFixed(0)}`
              : '--'}
          </div>
        </div>
        <div style={{ ...card, flex: 1 }}>
          <div style={{ color: '#888', fontSize: 12 }}>负债率</div>
          <div style={{ fontSize: 14 }}>
            {financial?.debt_ratio?.toFixed(1) || '--'}%
          </div>
        </div>
      </div>
    </div>
  )
}
