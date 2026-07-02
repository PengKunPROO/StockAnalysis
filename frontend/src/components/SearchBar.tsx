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
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleInput = async (val: string) => {
    setQuery(val)
    if (val.length >= 1) {
      try {
        const data = await searchStocks(val)
        setResults(data.results)
        setOpen(true)
      } catch { setOpen(false) }
    } else {
      setOpen(false)
    }
  }

  const select = async (s: StockInfo) => {
    dispatch({ type: 'SET_STOCK', stock: s })
    setQuery(s.name)
    setOpen(false)
    // Add to watchlist if not already there
    if (!state.watchlist.find(w => w.code === s.code)) {
      try {
        await addToWatchlist(s.code, s.name)
        const { getWatchlist } = await import('../api/watchlist')
        const d = await getWatchlist()
        dispatch({ type: 'SET_WATCHLIST', watchlist: d.stocks })
      } catch {}
    }
  }

  return (
    <div ref={ref} className="search-wrap" style={{ position: 'relative', width: '100%' }}>
      <input
        value={query}
        onChange={e => handleInput(e.target.value)}
        placeholder="搜索股票代码或名称..."
      />
      {open && results.length > 0 && (
        <div className="search-dropdown">
          {results.map(s => (
            <div key={s.code} className="item" onClick={() => select(s)}>
              <span><strong>{s.name}</strong></span>
              <span className="code">{s.code}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
