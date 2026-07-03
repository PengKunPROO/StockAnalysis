import { useEffect, useRef } from 'react'
import { createChart, ColorType, CrosshairMode, CandlestickSeries, HistogramSeries } from 'lightweight-charts'
import { useApp } from '../contexts/AppContext'
import { getKline } from '../api/stocks'
import type { KlineBar } from '../types'

export default function KlineChart() {
  const { state } = useApp()
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<any>(null)
  const candleSeriesRef = useRef<any>(null)
  const volumeSeriesRef = useRef<any>(null)

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
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    })
    volumeSeriesRef.current = volumeSeries
    chart.priceScale('').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } })

    return () => chart.remove()
  }, [state.currentStock])

  useEffect(() => {
    if (!state.currentStock || !candleSeriesRef.current) return
    const code = state.currentStock.code

    getKline(code, 'daily', '2025-01-01', '2026-12-31').then(({ data }) => {
      const candles = data.map((d: KlineBar) => ({
        time: d.date,
        open: d.open, high: d.high, low: d.low, close: d.close,
      }))
      const volumes = data.map((d: KlineBar) => ({
        time: d.date,
        value: d.volume,
        color: d.close >= d.open ? 'rgba(38,166,154,0.3)' : 'rgba(239,83,80,0.3)',
      }))
      candleSeriesRef.current.setData(candles)
      volumeSeriesRef.current.setData(volumes)
      chartRef.current?.timeScale().fitContent()
    })
  }, [state.currentStock])

  return (
    <div className="kline-container">
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
    </div>
  )
}
