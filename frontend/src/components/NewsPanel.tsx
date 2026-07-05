import { useState, useEffect } from 'react'
import { useApp } from '../contexts/AppContext'

interface NewsItem {
  id?: number; title: string; source: string; url?: string; summary?: string; published_at?: string
}

export default function NewsPanel() {
  const { state } = useApp()
  const stock = state.currentStock
  const [news, setNews] = useState<NewsItem[]>([])
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [analyzing, setAnalyzing] = useState<number | null>(null)
  const [analysis, setAnalysis] = useState('')
  const [error, setError] = useState('')
  const [days, setDays] = useState(7)

  useEffect(() => { if (stock) fetchNews() }, [stock])

  const fetchNews = async (refresh = false) => {
    if (!stock) return
    setLoading(true)
    try {
      const params = new URLSearchParams({ limit: '15', days: String(days) })
      if (refresh) params.set('refresh', 'true')
      const r = await fetch(`/api/v1/news/stock/${stock.code}?${params}`)
      const d = await r.json()
      if (d.news && d.news.length > 0) {
        setNews(d.news)
        setError('')
      } else {
        setError(d.error || '暂无相关新闻')
      }
    } catch { setError('获取新闻失败') }
    setLoading(false)
  }

  const toggleExpand = (idx: number) => {
    setExpanded(expanded === idx ? null : idx)
    setAnalyzing(null)
  }

  const analyze = async (idx: number) => {
    const item = news[idx]
    if (!item || !stock) return
    setAnalyzing(idx); setAnalysis('')
    try {
      const r = await fetch(`/api/v1/news/stock/${stock.code}/analyze`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: item.title, source: item.source, summary: item.summary || '' }),
      })
      const reader = r.body!.getReader(); const dec = new TextDecoder(); let buf = ''
      while (true) {
        const { done, value } = await reader.read(); if (done) break
        buf += dec.decode(value, { stream: true })
        const lines = buf.split('\n'); buf = lines.pop() || ''
        for (const l of lines) {
          if (l.startsWith('data: ')) {
            try { const j = JSON.parse(l.slice(6)); if (j.done) return; if (j.content) setAnalysis(p => p + j.content) } catch {}
          }
        }
      }
    } catch (e: any) { if (e.name !== 'AbortError') setAnalysis('分析失败: ' + e.message) }
  }

  const fmtDate = (pubAt: string) => {
    if (!pubAt) return ''
    const d = pubAt.slice(0, 10)
    if (d === new Date().toISOString().slice(0, 10)) return '今天 ' + pubAt.slice(11, 16)
    const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10)
    if (d === yesterday) return '昨天 ' + pubAt.slice(11, 16)
    return d
  }

  if (!stock) return null

  return (
    <div className="news-panel">
      <div className="nhd">
        <span>📰 {stock.name} 相关新闻</span>
        <select value={days} onChange={e => { setDays(Number(e.target.value)); fetchNews(true) }}
          style={{ marginLeft: 'auto', border: '1px solid var(--border)', background: 'var(--surf2)', color: 'var(--h)', fontSize: 11, padding: '2px 6px', borderRadius: 4 }}>
          <option value={1}>近1天</option><option value={3}>近3天</option><option value={7}>近7天</option><option value={14}>近14天</option><option value={30}>近30天</option>
        </select>
        <button onClick={() => fetchNews(true)} disabled={loading}
          style={{ marginLeft: 4, padding: '2px 10px', borderRadius: 4, border: '1px solid var(--acc)', background: 'transparent', color: 'var(--acc)', fontSize: 11, cursor: 'pointer' }}>
          {loading ? '搜索中...' : '刷新'}
        </button>
      </div>
      {error && <div style={{ color: 'var(--down)', fontSize: 12, margin: '6px 0', textAlign: 'center' }}>{error}</div>}
      <div style={{ maxHeight: 400, overflowY: 'auto' }}>
        {news.map((item, i) => (
          <div key={i}>
            <div className="news-item" onClick={() => toggleExpand(i)}>
              <div className="dot" />
              <div className="txt">
                <div className="t">{item.title}</div>
                <div className="s">
                  <span>{item.source}</span>
                  {item.published_at && <span>{fmtDate(item.published_at)}</span>}
                </div>
              </div>
              <div className="arr">▸</div>
            </div>
            {expanded === i && (
              <div className="news-detail">
                {item.summary && <p className="ns">{item.summary}</p>}
                <div className="na">
                  {item.url && (
                    <a href={item.url} target="_blank" rel="noopener" className="nl" onClick={e => e.stopPropagation()}>
                      🔗 阅读原文
                    </a>
                  )}
                  <button className="abtn" onClick={e => { e.stopPropagation(); analyze(i) }}>
                    🤖 AI分析
                  </button>
                </div>
                {analyzing === i && (
                  <div className="news-analysis">{analysis || '分析中...'}</div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
