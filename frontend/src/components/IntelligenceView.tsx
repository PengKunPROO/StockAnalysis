import { useEffect, useState, useCallback } from 'react'
import { useApp } from '../contexts/AppContext'
import {
  getOverview, getLimitUp, getFundFlow, getSectors, getDragonTiger,
  getAnomalies, getAnnouncements,
} from '../api/intelligence'
import type { Overview, SectorItem, NorthFlow } from '../api/intelligence'

type Tab = 'limit-up' | 'fund-flow' | 'sectors' | 'dragon-tiger' | 'anomalies' | 'announcements'
const TABS: { key: Tab; label: string }[] = [
  { key: 'limit-up', label: '连板梯队' },
  { key: 'fund-flow', label: '资金流' },
  { key: 'sectors', label: '板块轮动' },
  { key: 'dragon-tiger', label: '龙虎榜' },
  { key: 'anomalies', label: '异动' },
  { key: 'announcements', label: '公告' },
]

export default function IntelligenceView() {
  const { dispatch } = useApp()
  const [overview, setOverview] = useState<Overview | null>(null)
  const [tab, setTab] = useState<Tab>('limit-up')

  useEffect(() => {
    getOverview().then(setOverview).catch(() => {})
    const id = setInterval(() => getOverview().then(setOverview).catch(() => {}), 60000)
    return () => clearInterval(id)
  }, [])

  const openStock = (code: string, name: string) => {
    dispatch({ type: 'SET_STOCK', stock: { code, name, market: 'a_share', industry: '' } })
    dispatch({ type: 'SET_VIEW', view: 'stock' })
  }

  return (
    <div className="intelligence-view">
      {overview && <Dashboard ov={overview} />}
      <div className="intel-tabs">
        <span className="intel-title">市场情报</span>
        {TABS.map(t => (
          <button key={t.key} className={tab === t.key ? 'active' : ''} onClick={() => setTab(t.key)}>{t.label}</button>
        ))}
      </div>
      <div className="intel-content">
        {tab === 'limit-up' && <LimitUpTab onOpen={openStock} />}
        {tab === 'fund-flow' && <FundFlowTab />}
        {tab === 'sectors' && <SectorsTab onOpen={openStock} />}
        {tab === 'dragon-tiger' && <DragonTigerTab onOpen={openStock} />}
        {tab === 'anomalies' && <AnomaliesTab onOpen={openStock} />}
        {tab === 'announcements' && <AnnouncementsTab onOpen={openStock} />}
      </div>
    </div>
  )
}

function Dashboard({ ov }: { ov: Overview }) {
  return (
    <div className="intel-dashboard">
      <div className="index-cards">
        {ov.indices.map(idx => {
          const up = idx.change_pct >= 0
          return (
            <div key={idx.code} className="index-card">
              <div className="idx-name">{idx.name}</div>
              <div className="idx-price">{idx.price?.toFixed(2) || '--'}</div>
              <div className="idx-change" style={{ color: up ? 'var(--up)' : 'var(--down)' }}>
                {up ? '▲' : '▼'} {Math.abs(idx.change_pct || 0).toFixed(2)}%
              </div>
            </div>
          )
        })}
      </div>
      <div className="stats-bar">
        <span className="up">上涨 {ov.breadth.up}</span>
        <span className="down">下跌 {ov.breadth.down}</span>
        <span className="up">涨停 {ov.breadth.limit_up}</span>
        <span className="down">跌停 {ov.breadth.limit_down}</span>
        <span className="gold">平盘 {ov.breadth.flat}</span>
        <span className="red-ratio">
          <span className="ratio-bar"><span className="ratio-fill" style={{ width: `${ov.red_ratio}%` }} /></span>
          {ov.red_ratio}% 红盘占比
        </span>
      </div>
      <div className="sentiment-bar">
        <div className="sent-item">
          <span className="sent-label">恐惧贪婪</span>
          <span className="sent-bar"><span className="sent-marker" style={{ left: `${ov.sentiment.fear_greed}%` }} /></span>
          <span className="sent-value" style={{ color: ov.sentiment.fear_greed >= 65 ? 'var(--up)' : ov.sentiment.fear_greed <= 35 ? 'var(--down)' : 'var(--gold)' }}>
            {ov.sentiment.fear_greed}/100 {ov.sentiment.fear_greed_label}
          </span>
        </div>
        <span className="sent-stat">赚钱效应 <b className="accent">{ov.sentiment.profit_effect}%</b></span>
        <span className="sent-stat">打板成功率 <b className="accent">{ov.sentiment.seal_success_rate ?? '--'}%</b></span>
        <span className="sent-stat">连板晋级率 <b className="gold">{ov.sentiment.promotion_rate ?? '--'}%</b></span>
      </div>
    </div>
  )
}

function useTabData<T>(fetcher: () => Promise<T>, deps: any[] = []) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(false)
  const load = useCallback(async () => {
    setLoading(true)
    try { setData(await fetcher()) } catch { setData(null) }
    finally { setLoading(false) }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  useEffect(() => { load() }, [load])
  return { data, loading }
}

function LimitUpTab({ onOpen }: { onOpen: (code: string, name: string) => void }) {
  const { data, loading } = useTabData(() => getLimitUp(), [])
  if (loading) return <div className="intel-loading">加载中...</div>
  if (!data) return <div className="intel-loading">数据不可用</div>
  if (data.warning && !data.stocks.length) return <div className="intel-loading">{data.warning}</div>
  const buckets = Object.entries(data.buckets).sort((a, b) => {
    const order = (k: string) => (k === '高位板' ? 99 : parseInt(k) || 0)
    return order(b[0]) - order(a[0])
  })
  return (
    <div>
      <div className="bucket-row">
        {buckets.map(([k, v]) => (
          <div key={k} className={`bucket ${k === '高位板' ? 'hot' : k === '1板' ? 'fresh' : ''}`}>
            <div className="bucket-num">{v}</div><div className="bucket-label">{k}</div>
          </div>
        ))}
        <div className="bucket-total">合计涨停 {data.count} 只</div>
      </div>
      <table className="intel-table">
        <thead><tr><th>代码</th><th>名称</th><th className="r">连板</th><th className="r">涨幅</th><th className="r">封板金额(亿)</th><th className="r">炸板</th><th className="c"></th></tr></thead>
        <tbody>
          {data.stocks.map(s => (
            <tr key={s.code} onClick={() => onOpen(s.code, s.name)}>
              <td className="code">{s.code.split('.')[1]}</td>
              <td className="name">{s.name}</td>
              <td className="r accent">{s.consecutive_days}</td>
              <td className="r up">{(s.change_pct || 0).toFixed(2)}%</td>
              <td className="r muted">{s.seal_amount ? (s.seal_amount * 1e-8).toFixed(2) : '-'}</td>
              <td className="r muted">{s.broken_count}</td>
              <td className="c accent">→</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function FundFlowTab() {
  const [scope, setScope] = useState<'industry' | 'concept' | 'north' | 'stock'>('industry')
  const { data, loading } = useTabData(() => getFundFlow(scope), [scope])
  if (loading) return <div className="intel-loading">加载中...</div>
  if (!data) return <div className="intel-loading">数据不可用</div>
  if (data.warning && !data.sectors && !data.north && !data.stocks) return <div className="intel-loading">{data.warning}</div>
  return (
    <div>
      <div className="sub-tabs">
        {(['industry', 'concept', 'north', 'stock'] as const).map(s => (
          <button key={s} className={scope === s ? 'active' : ''} onClick={() => setScope(s)}>
            {s === 'industry' ? '行业' : s === 'concept' ? '概念' : s === 'north' ? '北向资金' : '个股'}
          </button>
        ))}
      </div>
      {scope === 'north' ? (
        <table className="intel-table">
          <thead><tr><th>日期</th><th className="r">沪股通(亿)</th><th className="r">深股通(亿)</th><th className="r">合计(亿)</th></tr></thead>
          <tbody>
            {(data.north || []).map((n: NorthFlow) => (
              <tr key={n.date}>
                <td>{n.date}</td>
                <td className="r" style={{ color: n.sh_connect_net >= 0 ? 'var(--up)' : 'var(--down)' }}>{(n.sh_connect_net * 1e-8).toFixed(2)}</td>
                <td className="r" style={{ color: n.sz_connect_net >= 0 ? 'var(--up)' : 'var(--down)' }}>{(n.sz_connect_net * 1e-8).toFixed(2)}</td>
                <td className="r" style={{ color: n.total_net >= 0 ? 'var(--up)' : 'var(--down)' }}>{(n.total_net * 1e-8).toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : scope === 'stock' ? (
        <table className="intel-table">
          <thead><tr><th>代码</th><th>名称</th><th className="r">成交额(亿)</th><th className="r">涨幅</th></tr></thead>
          <tbody>
            {(data.stocks || []).map((s: any) => (
              <tr key={s.code}><td className="code">{s.code.split('.')[1]}</td><td className="name">{s.name}</td><td className="r">{s.amount}</td><td className="r" style={{ color: s.change_pct >= 0 ? 'var(--up)' : 'var(--down)' }}>{s.change_pct?.toFixed(2)}%</td></tr>
            ))}
          </tbody>
        </table>
      ) : (
        <table className="intel-table">
          <thead><tr><th>板块</th><th className="r">涨跌幅</th><th className="r">上涨</th><th className="r">下跌</th><th className="r">主力净流入(亿)</th></tr></thead>
          <tbody>
            {(data.sectors || []).map((s: SectorItem) => (
              <tr key={s.code}>
                <td className="name">{s.name}</td>
                <td className="r" style={{ color: s.change_pct >= 0 ? 'var(--up)' : 'var(--down)' }}>{s.change_pct?.toFixed(2)}%</td>
                <td className="r up">{s.up_count ?? '-'}</td>
                <td className="r down">{s.down_count ?? '-'}</td>
                <td className="r" style={{ color: (s.main_net || 0) >= 0 ? 'var(--up)' : 'var(--down)' }}>{s.main_net ? (s.main_net * 1e-8).toFixed(2) : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function SectorsTab({ onOpen }: { onOpen: (code: string, name: string) => void }) {
  const [type, setType] = useState<'industry' | 'concept'>('industry')
  const { data, loading } = useTabData(() => getSectors(type), [type])
  if (loading) return <div className="intel-loading">加载中...</div>
  if (!data || (!data.sectors.length && data.warning)) return <div className="intel-loading">{data?.warning || '数据不可用'}</div>
  return (
    <div>
      <div className="sub-tabs">
        {(['industry', 'concept'] as const).map(t => (
          <button key={t} className={type === t ? 'active' : ''} onClick={() => setType(t)}>{t === 'industry' ? '行业板块' : '概念板块'}</button>
        ))}
      </div>
      <div className="sector-grid">
        {(data?.sectors || []).map(s => {
          const up = s.change_pct >= 0
          return (
            <div key={s.code} className={`sector-card ${up ? 'up' : 'down'}`} onClick={() => onOpen(s.code, s.name)}>
              <div className="sector-name">{s.name}</div>
              <div className="sector-change">{up ? '+' : ''}{s.change_pct?.toFixed(2)}%</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function DragonTigerTab({ onOpen }: { onOpen: (code: string, name: string) => void }) {
  const { data, loading } = useTabData(() => getDragonTiger(), [])
  if (loading) return <div className="intel-loading">加载中...</div>
  if (!data || (!data.stocks.length && data.warning)) return <div className="intel-loading">{data?.warning || '当日龙虎榜尚未更新'}</div>
  return (
    <table className="intel-table">
      <thead><tr><th>代码</th><th>名称</th><th>日期</th><th className="r">涨幅</th><th>上榜原因</th><th className="c"></th></tr></thead>
      <tbody>
        {data.stocks.map(s => (
          <tr key={s.code + s.date} onClick={() => onOpen(s.code, s.name)}>
            <td className="code">{s.code.split('.')[1]}</td>
            <td className="name">{s.name}</td>
            <td className="muted">{s.date}</td>
            <td className="r" style={{ color: (s.change_pct || 0) >= 0 ? 'var(--up)' : 'var(--down)' }}>{s.change_pct?.toFixed(2)}%</td>
            <td className="muted small">{s.reason}</td>
            <td className="c accent">→</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

const ANOMALY_COLOR: Record<string, string> = {
  涨停: 'var(--up)', 跌停: 'var(--down)', 振幅异动: 'var(--gold)', 急涨: 'var(--up)', 急跌: 'var(--down)',
}

function AnomaliesTab({ onOpen }: { onOpen: (code: string, name: string) => void }) {
  const [filter, setFilter] = useState<string>('all')
  const { data, loading } = useTabData(() => getAnomalies(50), [])
  if (loading) return <div className="intel-loading">加载中...</div>
  if (!data || (!data.anomalies.length && data.warning)) return <div className="intel-loading">{data?.warning || '数据不可用'}</div>
  const types = ['all', ...Array.from(new Set(data.anomalies.map(a => a.type)))]
  const list = filter === 'all' ? data.anomalies : data.anomalies.filter(a => a.type === filter)
  return (
    <div>
      <div className="sub-tabs">
        {types.map(t => <button key={t} className={filter === t ? 'active' : ''} onClick={() => setFilter(t)}>{t === 'all' ? '全部' : t}</button>)}
      </div>
      <table className="intel-table">
        <thead><tr><th>代码</th><th>名称</th><th className="r">涨幅</th><th className="r">振幅</th><th className="r">换手</th><th>类型</th><th className="c"></th></tr></thead>
        <tbody>
          {list.map(a => (
            <tr key={a.code + a.type} onClick={() => onOpen(a.code, a.name)}>
              <td className="code">{a.code.split('.')[1]}</td>
              <td className="name">{a.name}</td>
              <td className="r" style={{ color: a.change_pct >= 0 ? 'var(--up)' : 'var(--down)' }}>{a.change_pct?.toFixed(2)}%</td>
              <td className="r muted">{a.amplitude?.toFixed(2)}%</td>
              <td className="r muted">{a.turnover?.toFixed(2)}%</td>
              <td><span className="anomaly-badge" style={{ background: `${ANOMALY_COLOR[a.type] || 'var(--muted)'}33`, color: ANOMALY_COLOR[a.type] || 'var(--muted)' }}>{a.type}</span></td>
              <td className="c accent">→</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function AnnouncementsTab({ onOpen }: { onOpen: (code: string, name: string) => void }) {
  const { data, loading } = useTabData(() => getAnnouncements(20), [])
  if (loading) return <div className="intel-loading">加载中...</div>
  if (!data || (!data.announcements.length && data.warning)) return <div className="intel-loading">{data?.warning || '数据不可用'}</div>
  return (
    <div className="ann-list">
      {data.announcements.map((a, i) => (
        <div key={i} className="ann-item" onClick={() => onOpen(a.code, a.stock)}>
          <div className="ann-head"><span className="ann-stock">{a.stock}</span><span className="ann-date">{a.date?.slice(0, 10)}</span></div>
          <div className="ann-title">{a.title}</div>
        </div>
      ))}
    </div>
  )
}
