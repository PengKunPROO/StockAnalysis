import { get, post } from './client'

export interface FilterField {
  name: string
  label: string
  type: 'number_range' | 'boolean' | 'choice'
  category: string
  unit: string
  constraints: Record<string, any>
  available: boolean
  description?: string
  source?: string
  pass_phase?: number
}

export interface ScreenerSkill {
  name: string
  label: string
  description: string
  fields: Record<string, any>
}

export interface FactorDetail {
  actual: number | boolean | null
  threshold: any
  pass: boolean
}

export interface ScreenResult {
  code: string
  name: string
  price?: number
  change_pct?: number
  turnover?: number
  amount?: number
  amplitude?: number
  open?: number
  high?: number
  low?: number
  pe_ttm?: number
  pb?: number
  roe?: number
  debt_ratio?: number
  total_market_cap?: number
  signals?: string[]
  score?: number
  near_high_drop?: number
  change_5d?: number
  change_20d?: number
  on_dragon_tiger?: boolean
  hot_rank?: number | null
  main_net_flow?: number | null
  factor_details?: Record<string, FactorDetail>
}

export type FieldValue = { min?: number; max?: number } | boolean

export const getScreenerFields = () =>
  get<{ fields: FilterField[]; categories: string[] }>('/screener/fields')

export const getScreenerSkills = () =>
  get<{ skills: ScreenerSkill[] }>('/screener/skills')

export const runScreener = (fields: Record<string, FieldValue>, sort = 'change_pct', limit = 50) =>
  post<{ results: ScreenResult[]; count: number; warning?: string }>('/screener/run', {
    fields, sort, limit,
  })
