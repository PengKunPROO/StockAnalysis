import { useEffect, useRef, useState } from 'react'
import { createChart, ColorType, CrosshairMode, CandlestickSeries, HistogramSeries } from 'lightweight-charts'
import { useApp } from '../contexts/AppContext'
import { getKline } from '../api/stocks'
import type { KlineBar } from '../types'

function today(): string { return new Date().toISOString().slice(0, 10) }

export default function KlineChart() {
  const { state } = useApp()
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<any>(null)
  const candleRef = useRef<any>(null)
  const volRef = useRef<any>(null)
  const reqIdRef = useRef(0)
  const priceLinesRef = useRef<any[]>([])
  const [loading, setLoading] = useState(false)
  const [showLevels, setShowLevels] = useState(true)

  // Create chart once on mount — never destroy on stock switch
  useEffect(() => {
    if (!containerRef.current || chartRef.current) return

    const chart = createChart(containerRef.current, {
      layout: { background: { type: ColorType.Solid, color: '#0a0a20' }, textColor: '#c8c8e0' },
      grid: { vertLines: { color: '#1a1a3a' }, horzLines: { color: '#1a1a3a' } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: '#1a1a3a' },
      timeScale: { borderColor: '#1a1a3a', timeVisible: true },
    })
    chartRef.current = chart

    const cs = chart.addSeries(CandlestickSeries, {
      upColor: '#00e5ff', downColor: '#ff3366', borderUpColor: '#00e5ff', borderDownColor: '#ff3366',
      wickUpColor: '#00e5ff', wickDownColor: '#ff3366',
    })
    candleRef.current = cs
    const vs = chart.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, priceScaleId: '' })
    volRef.current = vs
    chart.priceScale('').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } })

    return () => chart.remove()
  }, [])

  // Load/update data when stock changes
  useEffect(() => {
    const code = state.currentStock?.code
    if (!code) return

    const id = ++reqIdRef.current
    setLoading(true)

    const load = async () => {
      const end = today()
      const start = `${parseInt(end.slice(0, 4)) - 1}${end.slice(4)}`
      try {
        const { data } = await getKline(code, 'daily', start, end)
        if (id !== reqIdRef.current) return // stale
        const candles = data.map((d: KlineBar) => ({
          time: d.date, open: d.open, high: d.high, low: d.low, close: d.close,
        }))
        const volumes = data.map((d: KlineBar) => ({
          time: d.date, value: d.volume,
          color: d.close >= d.open ? 'rgba(38,166,154,0.3)' : 'rgba(239,83,80,0.3)',
        }))
        candleRef.current?.setData(candles)
        volRef.current?.setData(volumes)
        chartRef.current?.timeScale().fitContent()
      } finally {
        if (id === reqIdRef.current) setLoading(false)
      }
    }
    load()
  }, [state.currentStock?.code])

  const refresh = () => {
    const code = state.currentStock?.code
    if (!code) return
    // reset reqId to force accept the next response
    const id = ++reqIdRef.current
    setLoading(true)
    const load = async () => {
      const end = today()
      const start = `${parseInt(end.slice(0, 4)) - 1}${end.slice(4)}`
      try {
        const { data } = await getKline(code, 'daily', start, end)
        if (id !== reqIdRef.current) return
        candleRef.current?.setData(data.map((d: KlineBar) => ({ time: d.date, open: d.open, high: d.high, low: d.low, close: d.close })))
        volRef.current?.setData(data.map((d: KlineBar) => ({ time: d.date, value: d.volume, color: d.close >= d.open ? 'rgba(38,166,154,0.3)' : 'rgba(239,83,80,0.3)' })))
        chartRef.current?.timeScale().fitContent()
      } finally { if (id === reqIdRef.current) setLoading(false) }
    }
    load()
  }

  // Draw support/resistance/fibonacci price lines from signals
  useEffect(() => {
    const series = candleRef.current
    if (!series) return
    // clear existing
    for (const pl of priceLinesRef.current) {
      try { series.removePriceLine(pl) } catch {}
    }
    priceLinesRef.current = []
    if (!showLevels) return
    const levels = state.signals?.key_levels || []
    const colorFor = (type: string) =>
      type === '阻力' ? '#22c55e' : type === '斐波' ? '#f59e0b' : '#ef4444'
    for (const lvl of levels.slice(0, 6)) {
      try {
        const pl = series.createPriceLine({
          price: lvl.price,
          color: colorFor(lvl.type),
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: true,
          title: lvl.type,
        })
        priceLinesRef.current.push(pl)
      } catch {}
    }
  }, [state.signals, showLevels])

  return (
    <div className="kline-container" style={{ position: 'relative' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      <button onClick={refresh} disabled={loading}
        style={{ position: 'absolute', top: 6, right: 8, zIndex: 10, padding: '2px 8px', borderRadius: 4, border: '1px solid var(--border)', background: 'rgba(10,10,32,.8)', color: loading ? 'var(--muted)' : 'var(--accent)', fontSize: 10, cursor: loading ? 'default' : 'pointer' }}
        title="刷新K线数据">{loading ? '加载中...' : '↻ 刷新'}</button>
      <button onClick={() => setShowLevels(v => !v)}
        style={{ position: 'absolute', top: 6, right: 64, zIndex: 10, padding: '2px 8px', borderRadius: 4, border: '1px solid var(--border)', background: 'rgba(10,10,32,.8)', color: showLevels ? 'var(--accent)' : 'var(--muted)', fontSize: 10, cursor: 'pointer' }}
        title="切换支撑/阻力价位线">{showLevels ? '价位 ✓' : '价位 ✕'}</button>
    </div>
  )
}
