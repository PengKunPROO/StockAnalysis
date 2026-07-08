import { get, post } from './client'

export interface FilterField {
  name: string
  label: string
  type: 'number_range' | 'boolean' | 'choice'
  category: string
  unit: string
  constraints: Record<string, any>
  available: boolean
}

export interface ScreenerSkill {
  name: string
  label: string
  description: string
  fields: Record<string, any>
}

export interface ScreenResult {
  code: string
  name: string
  price?: number
  change_pct?: number
  turnover?: number
  amount?: number
  pe_ttm?: number
  pb?: number
  roe?: number
  total_market_cap?: number
  signals?: string[]
  score?: number
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
