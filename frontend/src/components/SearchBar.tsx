import { useState, useRef, useEffect } from 'react'
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
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h); return () => document.removeEventListener('mousedown', h)
  }, [])

  const handle = async (v: string) => {
    setQuery(v)
    if (v.length >= 1) { try { setResults((await searchStocks(v)).results); setOpen(true) } catch { setOpen(false) } }
    else setOpen(false)
  }

  const select = async (s: StockInfo) => {
    dispatch({ type: 'SET_STOCK', stock: s }); setQuery(s.name); setOpen(false)
    if (!state.watchlist.find(w => w.code === s.code)) {
      await addToWatchlist(s.code, s.name)
      dispatch({ type: 'SET_WATCHLIST', watchlist: (await (await import('../api/watchlist')).getWatchlist()).stocks })
    }
  }

  return (
    <div ref={ref} className="search-wrap">
      <input value={query} onChange={e => handle(e.target.value)} placeholder="搜索股票代码或名称..." />
      {open && results.length > 0 && (
        <div className="search-dropdown">
          {results.map(s => <div key={s.code} className="item" onClick={() => select(s)}><span>{s.name}</span><span className="code">{s.code}</span></div>)}
        </div>
      )}
    </div>
  )
}
