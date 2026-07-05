import { useState, useEffect, useRef } from 'react'
import { useApp } from '../contexts/AppContext'

interface NewsItem { id?:number; title:string; source:string; url?:string; summary?:string }

export default function NewsPanel() {
  const { state } = useApp()
  const stock = state.currentStock
  const [news, setNews] = useState<NewsItem[]>([])
  const [loading, setLoading] = useState(false)
  const [analyzing, setAnalyzing] = useState<number|null>(null)
  const [analysis, setAnalysis] = useState('')
  const [error, setError] = useState('')

  useEffect(() => { if (stock) fetchNews() }, [stock])

  const fetchNews = async () => {
    if (!stock) return
    setLoading(true); setError('')
    try { const d = await (await fetch(`/api/v1/news/stock/${stock.code}`)).json(); setNews(d.news||[]) } catch { setError('获取失败') }
    setLoading(false)
  }

  const analyze = async (item:NewsItem, idx:number) => {
    if (analyzing===idx) { setAnalyzing(null); return }
    setAnalyzing(idx); setAnalysis('')
    try {
      const r = await fetch(`/api/v1/news/stock/${stock!.code}/analyze`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({title:item.title,source:item.source,summary:item.summary||''})
      })
      const reader = r.body!.getReader(); const d = new TextDecoder(); let b = ''
      while(true) {
        const {done,value} = await reader.read(); if(done) break
        b += d.decode(value,{stream:true})
        const ls = b.split('\n'); b=ls.pop()||''
        for(const l of ls) if(l.startsWith('data: ')) try{const j=JSON.parse(l.slice(6));if(j.done)return;if(j.content)setAnalysis(p=>p+j.content)}catch{}
      }
    } catch(e:any) { if(e.name!=='AbortError') setAnalysis('分析失败') }
  }

  if (!stock) return null

  return (
    <div className="news-panel">
      <div className="nhd">
        <span>📰 相关新闻</span>
        <select style={{marginLeft:'auto',border:'1px solid var(--border)',background:'var(--surf2)',color:'var(--h)',fontSize:10,padding:'1px 4px',borderRadius:3}}><option>近3天</option><option>近7天</option></select>
        <button onClick={fetchNews} disabled={loading} title="刷新新闻">{loading?'搜索中...':'刷新'}</button>
      </div>
      {error && <div style={{color:'var(--down)',fontSize:10,margin:4}}>{error}</div>}
      {news.map((item,i)=>(
        <div key={i}>
          <div className="news-item" onClick={()=>analyze(item,i)}>
            <div className="dot"></div>
            <div className="txt"><div className="t">{item.title}</div><div className="s">{item.source}</div></div>
            <div className="arr">▸</div>
          </div>
          {analyzing===i && (
            <div className="news-analysis">{analysis||<span style={{color:'var(--muted)',fontStyle:'italic'}}>🤖 分析中...</span>}</div>
          )}
        </div>
      ))}
      {!loading && news.length===0 && !error && <div style={{color:'var(--muted)',fontSize:10,textAlign:'center',padding:6}}>暂无新闻</div>}
    </div>
  )
}
