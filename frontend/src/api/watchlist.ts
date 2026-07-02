import { get, post, del } from './client'
import type { WatchlistItem } from '../types'

export const getWatchlist = () => get<{ stocks: WatchlistItem[] }>('/watchlist')
export const addToWatchlist = (code: string, name: string) =>
  post('/watchlist', { code, name })
export const removeFromWatchlist = (code: string) => del(`/watchlist/${code}`)
