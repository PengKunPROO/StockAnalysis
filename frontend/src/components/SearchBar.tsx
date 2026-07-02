import { useState, useRef, useEffect } from 'react'
import { searchStocks } from '../api/stocks'
import { useApp } from '../contexts/AppContext'
import type { StockInfo } from '../types'

export default function SearchBar() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<StockInfo[]>([])
  const [open, setOpen] = useState(false)
  const { dispatch } = useApp()
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
      const data = await searchStocks(val)
      setResults(data.results)
      setOpen(true)
    } else {
      setOpen(false)
    }
  }

  const select = (s: StockInfo) => {
    dispatch({ type: 'SET_STOCK', stock: s })
    setQuery(s.name)
    setOpen(false)
  }

  return (
    <div ref={ref} style={{ position: 'relative', margin: '8px 0' }}>
      <input
        value={query}
        onChange={e => handleInput(e.target.value)}
        placeholder="输入股票代码或名称..."
        style={{ width: '100%', padding: 10, fontSize: 16, borderRadius: 8, border: '1px solid #444', background: '#222', color: '#eee' }}
      />
      {open && results.length > 0 && (
        <div style={{ position: 'absolute', top: 44, left: 0, right: 0, background: '#333', borderRadius: 8, zIndex: 100, maxHeight: 300, overflowY: 'auto' }}>
          {results.map(s => (
            <div
              key={s.code}
              onClick={() => select(s)}
              style={{ padding: '8px 12px', cursor: 'pointer', borderBottom: '1px solid #444' }}
              onMouseEnter={e => (e.currentTarget.style.background = '#555')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            >
              <span style={{ fontWeight: 600 }}>{s.name}</span>
              <span style={{ color: '#999', marginLeft: 8 }}>{s.code}</span>
              <span style={{ color: '#888', marginLeft: 8 }}>{s.market === 'a_share' ? 'A股' : '美股'}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
