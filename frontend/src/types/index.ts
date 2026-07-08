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
  atr: { atr14: number } | null
}

export interface FibonacciLevels {
  high: number
  low: number
  direction: 'up' | 'down'
  levels: Record<string, number>
  window: number
}

export interface ActiveSignal {
  name: string
  direction: 'bull' | 'bear'
  strength: '强' | '中' | '弱'
  detail: string
  date: string
}

export interface SignalScore {
  value: number
  pct: number
  label: string
}

export interface KeyLevel {
  price: number
  type: string
  source: string
  note: string
}

export interface SignalRisk {
  atr: number
  stop_loss: number
  stop_loss_pct: number
  take_profit: number
  take_profit_pct: number
  kelly_pct: number
  risk_reward_ratio: number
}

export interface SignalsPayload {
  code: string
  active_signals: ActiveSignal[]
  score: SignalScore
  key_levels: KeyLevel[]
  risk: SignalRisk | null
  summary: string
  warning?: string
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
