import { useState, useRef, useEffect, useCallback } from 'react'
import { searchStocks } from '../api/stocks'
import { useApp } from '../contexts/AppContext'
import { addToWatchlist } from '../api/watchlist'
import type { StockInfo } from '../types'

export default function SearchBar() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<StockInfo[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [activeIdx, setActiveIdx] = useState(-1)
  const { state, dispatch } = useApp()
  const ref = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const timer = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h); return () => document.removeEventListener('mousedown', h)
  }, [])

  const doSearch = useCallback(async (v: string) => {
    if (v.trim().length < 1) { setOpen(false); setResults([]); return }
    setLoading(true)
    try {
      const data = await searchStocks(v.trim())
      setResults(data.results || [])
      setActiveIdx(-1)
      setOpen(true)
    } catch { setOpen(false) }
    setLoading(false)
  }, [])

  const handleChange = (v: string) => {
    setQuery(v)
    setActiveIdx(-1)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => doSearch(v), 250)
  }

  const select = useCallback(async (s: StockInfo) => {
    dispatch({ type: 'SET_STOCK', stock: s })
    dispatch({ type: 'SET_VIEW', view: 'stock' })
    setQuery(s.name); setOpen(false); setResults([])
    inputRef.current?.blur()
    if (!state.watchlist.find(w => w.code === s.code)) {
      try {
        await addToWatchlist(s.code, s.name)
        const { getWatchlist } = await import('../api/watchlist')
        dispatch({ type: 'SET_WATCHLIST', watchlist: (await getWatchlist()).stocks })
      } catch {}
    }
  }, [state.watchlist, dispatch])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open || results.length === 0) return
    if (e.key === 'ArrowDown') { e.preventDefault(); setActiveIdx(i => Math.min(i + 1, results.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActiveIdx(i => Math.max(i - 1, -1)) }
    else if (e.key === 'Enter') {
      e.preventDefault()
      if (activeIdx >= 0) select(results[activeIdx])
      else if (results.length > 0) select(results[0])
    }
    else if (e.key === 'Escape') { setOpen(false); inputRef.current?.blur() }
  }

  return (
    <div ref={ref} className="search-wrap">
      <input ref={inputRef} value={query}
        onChange={e => handleChange(e.target.value)}
        onKeyDown={handleKeyDown}
        onFocus={() => { if (results.length > 0) setOpen(true) }}
        placeholder="搜索股票代码或名称..." />
      {loading && <div className="search-spinner" />}
      {open && results.length > 0 && (
        <div className="search-dropdown">
          {results.map((s, i) => (
            <div key={s.code} className={`item ${i === activeIdx ? 'active' : ''}`}
              onMouseEnter={() => setActiveIdx(i)}
              onClick={() => select(s)}>
              <span>{s.name}</span><span className="code">{s.code}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
