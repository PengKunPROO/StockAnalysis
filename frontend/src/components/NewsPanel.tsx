import { useState, useEffect, useRef } from 'react'
import { useApp } from '../contexts/AppContext'

interface NewsItem {
  id?: number; title: string; source: string; url?: string; summary?: string; published_at?: string
}

export default function NewsPanel() {
  const { state } = useApp()
  const stock = state.currentStock
  const [news, setNews] = useState<NewsItem[]>([])
  const [loading, setLoading] = useState(false)
  const [analyzing, setAnalyzing] = useState<number | null>(null)
  const [analysis, setAnalysis] = useState('')
  const [error, setError] = useState('')

  useEffect(() => { if (stock) fetchNews() }, [stock])

  const fetchNews = async (refresh = false) => {
    if (!stock) return
    setLoading(true)
    try {
      const url = `/api/v1/news/stock/${stock.code}${refresh ? '?refresh=true' : ''}`
      const r = await fetch(url)
      const d = await r.json()
      if (d.news && d.news.length > 0) {
        setNews(d.news)
        setError('')
      } else {
        setError(d.error || '暂未找到相关新闻')
      }
    } catch { setError('获取新闻失败') }
    setLoading(false)
  }

  const analyze = async (item: NewsItem, idx: number) => {
    if (analyzing === idx) { setAnalyzing(null); return }
    setAnalyzing(idx); setAnalysis('')
    try {
      const r = await fetch(`/api/v1/news/stock/${stock!.code}/analyze`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: item.title, source: item.source, summary: item.summary || '' }),
      })
      const reader = r.body!.getReader(); const decoder = new TextDecoder(); let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n'); buf = lines.pop() || ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const d = JSON.parse(line.slice(6))
              if (d.done) return
              if (d.content) setAnalysis(prev => prev + d.content)
            } catch {}
          }
        }
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') setAnalysis('分析失败: ' + e.message)
    }
  }

  if (!stock) return null

  return (
    <div className="news-panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <span style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase' }}>📰 相关新闻</span>
        <button onClick={() => fetchNews(true)} disabled={loading}
          style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: 11 }}
          title="刷新新闻">{loading ? '搜索中...' : '刷新'}</button>
      </div>
      {error && <div style={{ color: 'var(--down)', fontSize: 11, marginBottom: 4 }}>{error}</div>}
      {news.map((item, i) => (
        <div key={i}>
          <div className="news-item" onClick={() => analyze(item, i)}>
            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.title}</span>
            <span style={{ color: 'var(--muted)', fontSize: 10, whiteSpace: 'nowrap' }}>{item.source}</span>
            {item.published_at && <span style={{ color: 'var(--muted)', fontSize: 9, whiteSpace: 'nowrap' }}>{item.published_at.slice(0, 10)}</span>}
          </div>
          {analyzing === i && (
            <div className="news-analysis">
              {analysis || <span style={{ color: 'var(--muted)', fontStyle: 'italic' }}>🤖 分析中...</span>}
            </div>
          )}
        </div>
      ))}
      {!loading && news.length === 0 && !error && (
        <div style={{ color: 'var(--muted)', fontSize: 11, textAlign: 'center', padding: 8 }}>暂无新闻，点击刷新获取</div>
      )}
    </div>
  )
}
