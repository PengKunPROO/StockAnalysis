import { get } from './client'

export interface MarketIndex {
  name: string
  code: string
  price: number
  change_pct: number
  volume?: number
}

export interface Overview {
  indices: MarketIndex[]
  breadth: { up: number; down: number; flat: number; limit_up: number; limit_down: number }
  red_ratio: number
  limit_up_count: number
  board_buckets: Record<string, number>
  sentiment: {
    fear_greed: number
    fear_greed_label: string
    profit_effect: number
    seal_success_rate: number | null
    promotion_rate: number | null
  }
  warning?: string
}

export interface LimitUpStock {
  code: string
  name: string
  price?: number
  change_pct?: number
  limit_up_time?: string
  reason?: string
  consecutive_days: number
  seal_amount?: number
}

export interface SectorItem {
  code: string
  name: string
  change_pct: number
  up_count?: number
  down_count?: number
  main_net?: number
}

export interface NorthFlow {
  date: string
  sh_connect_net: number
  sz_connect_net: number
  total_net: number
}

export interface DragonTigerStock {
  code: string
  name: string
  reason: string
  change_pct?: number
  net_buy?: number
}

export interface Anomaly {
  code: string
  name: string
  change_pct?: number | null
  type: string
  reason: string
  keywords?: string[]
}

export interface Announcement {
  stock: string
  code: string
  title: string
  date: string
  tag?: string
  heat?: number
}

export const getOverview = () => get<Overview>('/intelligence/overview')
export const getLimitUp = () =>
  get<{ stocks: LimitUpStock[]; buckets: Record<string, number>; count: number; ladder?: any[]; warning?: string }>('/intelligence/limit-up')
export const getFundFlow = (scope: 'north' | 'stock') =>
  get<Record<string, any>>(`/intelligence/fund-flow?scope=${scope}`)
export const getSectors = (type: 'industry' | 'concept') =>
  get<{ sectors: SectorItem[]; type: string; warning?: string }>(`/intelligence/sectors?type=${type}`)
export const getDragonTiger = (date = '') =>
  get<{ stocks: DragonTigerStock[]; count?: number; warning?: string }>(`/intelligence/dragon-tiger${date ? `?date=${date}` : ''}`)
export const getAnomalies = (limit = 50) =>
  get<{ anomalies: Anomaly[]; count: number; warning?: string }>(`/intelligence/anomalies?limit=${limit}`)
export const getAnnouncements = (limit = 20) =>
  get<{ announcements: Announcement[]; count: number; warning?: string }>(`/intelligence/announcements?limit=${limit}`)
