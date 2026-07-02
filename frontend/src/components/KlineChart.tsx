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
      layout: { background: { type: ColorType.Solid, color: '#1a1a2e' }, textColor: '#d1d4dc' },
      grid: { vertLines: { color: '#2a2a3e' }, horzLines: { color: '#2a2a3e' } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: '#2a2a3e' },
      timeScale: { borderColor: '#2a2a3e', timeVisible: true },
    })
    chartRef.current = chart

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#26a69a', downColor: '#ef5350', borderUpColor: '#26a69a', borderDownColor: '#ef5350',
      wickUpColor: '#26a69a', wickDownColor: '#ef5350',
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
    <div style={{ background: '#1a1a2e', borderRadius: 8, overflow: 'hidden' }}>
      <div ref={containerRef} style={{ width: '100%', height: 420 }} />
    </div>
  )
}
