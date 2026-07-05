export interface StockInfo {
  code: string
  name: string
  market: string
  industry: string
}

export interface KlineBar {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount: number
}

export interface IndicatorPoint {
  date: string
  macd: { dif: number; dea: number; macd: number } | null
  rsi: { rsi14: number } | null
  kdj: { k: number; d: number; j: number } | null
  boll: { upper: number; mid: number; lower: number } | null
}

export interface SkillMeta {
  name: string
  description: string
  mode: string
  filename?: string
  source?: string
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at?: string
}

export interface DiagnosisSession {
  id: string
  skill_name: string
  model: string
  created_at: string
  stocks: { code: string; name: string }[]
}

export interface WatchlistItem {
  code: string
  name: string
  market: string
  price?: number
  changePct?: number
}
