import { useEffect, useRef, useCallback, useState } from 'react'
import { createChart, ColorType, CrosshairMode, CandlestickSeries, HistogramSeries } from 'lightweight-charts'
import { useApp } from '../contexts/AppContext'
import { getKline } from '../api/stocks'
import type { KlineBar } from '../types'

function today(): string { return new Date().toISOString().slice(0, 10) }

export default function KlineChart() {
  const { state } = useApp()
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<any>(null)
  const candleSeriesRef = useRef<any>(null)
  const volumeSeriesRef = useRef<any>(null)
  const [loading, setLoading] = useState(false)

  const loadData = useCallback(async () => {
    if (!state.currentStock || !candleSeriesRef.current) return
    setLoading(true)
    try {
      const end = today()
      const start = `${parseInt(end.slice(0, 4)) - 2}${end.slice(4)}` // 2 years back
      const { data } = await getKline(state.currentStock.code, 'daily', start, end)
      const candles = data.map((d: KlineBar) => ({
        time: d.date, open: d.open, high: d.high, low: d.low, close: d.close,
      }))
      const volumes = data.map((d: KlineBar) => ({
        time: d.date, value: d.volume,
        color: d.close >= d.open ? 'rgba(38,166,154,0.3)' : 'rgba(239,83,80,0.3)',
      }))
      candleSeriesRef.current.setData(candles)
      volumeSeriesRef.current.setData(volumes)
      chartRef.current?.timeScale().fitContent()
    } finally { setLoading(false) }
  }, [state.currentStock])

  useEffect(() => {
    if (!state.currentStock || !containerRef.current) return

    const chart = createChart(containerRef.current, {
      layout: { background: { type: ColorType.Solid, color: '#0a0a20' }, textColor: '#c8c8e0' },
      grid: { vertLines: { color: '#1a1a3a' }, horzLines: { color: '#1a1a3a' } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: '#1a1a3a' },
      timeScale: { borderColor: '#1a1a3a', timeVisible: true },
    })
    chartRef.current = chart

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#00e5ff', downColor: '#ff3366', borderUpColor: '#00e5ff', borderDownColor: '#ff3366',
      wickUpColor: '#00e5ff', wickDownColor: '#ff3366',
    })
    candleSeriesRef.current = candleSeries

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' }, priceScaleId: '',
    })
    volumeSeriesRef.current = volumeSeries
    chart.priceScale('').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } })

    // Load data after chart is created
    setTimeout(() => loadData(), 0)

    return () => chart.remove()
  }, [state.currentStock])

  // Reload data when stock changes
  useEffect(() => {
    if (candleSeriesRef.current) loadData()
  }, [state.currentStock?.code])

  return (
    <div className="kline-container" style={{ position: 'relative' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      <button
        onClick={loadData}
        disabled={loading}
        style={{
          position: 'absolute', top: 6, right: 8, zIndex: 10,
          padding: '2px 8px', borderRadius: 4, border: '1px solid var(--border)',
          background: 'rgba(10,10,32,.8)', color: loading ? 'var(--muted)' : 'var(--accent)',
          fontSize: 10, cursor: loading ? 'default' : 'pointer',
        }}
        title="刷新K线数据"
      >
        {loading ? '加载中...' : '↻ 刷新'}
      </button>
    </div>
  )
}
