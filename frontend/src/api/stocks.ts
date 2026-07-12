import { get } from './client'
import type { StockInfo, KlineBar, IndicatorPoint } from '../types'

export const searchStocks = (q: string) =>
  get<{ results: StockInfo[]; count: number }>(`/search?q=${encodeURIComponent(q)}`)

export const getKline = (code: string, period = 'daily', start = '2024-01-01', end = '2026-12-31') =>
  get<{ code: string; data: KlineBar[]; count: number; warning?: string }>(`/stock/${code}/kline?period=${period}&start=${start}&end=${end}`)

export const getIndicators = (code: string, days = 60) =>
  get<{ code: string; data: IndicatorPoint[] }>(`/stock/${code}/indicators?days=${days}`)

export const getFinancial = (code: string) =>
  get<{ code: string; reports: any[] }>(`/stock/${code}/financial`)

export const getRealtime = (code: string) =>
  get<any>(`/stock/${code}/realtime`)
