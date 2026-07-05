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
  const timer = useRef<ReturnType<typeof setTimeout>>()
  const skipRef = useRef(false)

  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h); return () => document.removeEventListener('mousedown', h)
  }, [])

  const doSearch = async (v: string) => {
    if (v.length < 1) { setOpen(false); return }
    try { setResults((await searchStocks(v)).results); setOpen(true) } catch { setOpen(false) }
  }

  const handle = (v: string) => {
    setQuery(v)
    if (skipRef.current) { skipRef.current = false; setOpen(false); return }
    clearTimeout(timer.current)
    timer.current = setTimeout(() => doSearch(v), 300)
  }

  const select = async (s: StockInfo) => {
    skipRef.current = true
    dispatch({ type: 'SET_STOCK', stock: s })
    setQuery(s.name); setOpen(false)
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
