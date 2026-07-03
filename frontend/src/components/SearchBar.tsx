import { useState, useRef, useEffect } from 'react'
import { Input } from '@/components/ui/input'
import { searchStocks } from '../api/stocks'
import { useApp } from '../contexts/AppContext'
import { addToWatchlist } from '../api/watchlist'
import type { StockInfo } from '../types'

export default function SearchBar() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<StockInfo[]>([])
  const [open, setOpen] = useState(false)
  const { state, dispatch } = useApp()
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleInput = async (val: string) => {
    setQuery(val)
    if (val.length >= 1) {
      try { const data = await searchStocks(val); setResults(data.results); setOpen(true) } catch { setOpen(false) }
    } else { setOpen(false) }
  }

  const select = async (s: StockInfo) => {
    dispatch({ type: 'SET_STOCK', stock: s })
    setQuery(s.name)
    setOpen(false)
    if (!state.watchlist.find(w => w.code === s.code)) {
      try {
        await addToWatchlist(s.code, s.name)
        const { getWatchlist } = await import('../api/watchlist')
        dispatch({ type: 'SET_WATCHLIST', watchlist: (await getWatchlist()).stocks })
      } catch {}
    }
  }

  return (
    <div ref={ref} className="flex-1 max-w-[480px] relative">
      <Input value={query} onChange={e => handleInput(e.target.value)} placeholder="搜索股票代码或名称..." className="w-full" />
      {open && results.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-surface border border-border rounded-lg shadow-lg z-50 max-h-[300px] overflow-y-auto">
          {results.map(s => (
            <div key={s.code} onClick={() => select(s)} className="px-4 py-2.5 cursor-pointer hover:bg-gray-50 border-b border-border flex justify-between items-center transition-colors">
              <span className="font-medium text-sm">{s.name}</span>
              <span className="text-xs text-muted">{s.code}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
