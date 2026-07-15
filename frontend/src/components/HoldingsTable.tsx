// frontend/src/components/HoldingsTable.tsx
import { useState, useRef, useEffect } from 'react'
import type { Holding } from '../api/portfolio'
import { createHolding, stockLookup } from '../api/portfolio'

interface HoldingsTableProps {
  holdings: Holding[]
  realtimePrices: Record<string, { price: number; change_pct: number }>
  onDelete: (id: number) => void
  onSell: (holding: Holding) => void
  onRefresh?: () => void
}

export default function HoldingsTable({ holdings, realtimePrices, onDelete, onSell, onRefresh }: HoldingsTableProps) {
  const [showAdd, setShowAdd] = useState(false)
  const [addCode, setAddCode] = useState('')
  const [addName, setAddName] = useState('')
  const [addShares, setAddShares] = useState('')
  const [addCost, setAddCost] = useState('')
  const [addDate, setAddDate] = useState(new Date().toISOString().slice(0, 10))
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [nameLoading, setNameLoading] = useState(false)
  const codeTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const nameTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const autoFilled = useRef(false)

  const isAShare = addCode.startsWith('sh.') || addCode.startsWith('sz.')

  // Auto-fill stock name when code changes (debounced)
  useEffect(() => {
    if (codeTimer.current) clearTimeout(codeTimer.current)
    if (!addCode || addCode.length < 2) return
    if (autoFilled.current) { autoFilled.current = false; return }
    if (addName && (addCode.startsWith('sh.') || addCode.startsWith('sz.') || addCode.startsWith('us.'))) return
    codeTimer.current = setTimeout(async () => {
      setNameLoading(true)
      try {
        const data = await stockLookup(addCode)
        if (data.results.length > 0) {
          const best = data.results[0]
          autoFilled.current = true
          setAddCode(best.code)
          setAddName(best.name)
        }
      } catch { /* ignore */ } finally {
        setNameLoading(false)
      }
    }, 500)
    return () => { if (codeTimer.current) clearTimeout(codeTimer.current) }
  }, [addCode])

  // Auto-fill stock code when name changes (reverse lookup, debounced)
  useEffect(() => {
    if (nameTimer.current) clearTimeout(nameTimer.current)
    if (!addName || addName.trim().length < 2) return
    if (autoFilled.current) { autoFilled.current = false; return }
    if (addCode && (addCode.startsWith('sh.') || addCode.startsWith('sz.') || addCode.startsWith('us.'))) return
    nameTimer.current = setTimeout(async () => {
      setNameLoading(true)
      try {
        const data = await stockLookup(addName.trim())
        if (data.results.length > 0) {
          const best = data.results[0]
          autoFilled.current = true
          setAddCode(best.code)
          setAddName(best.name)
        }
      } catch { /* ignore */ } finally {
        setNameLoading(false)
      }
    }, 500)
    return () => { if (nameTimer.current) clearTimeout(nameTimer.current) }
  }, [addName])
  const sharesNum = parseInt(addShares, 10)
  const sharesInvalid = addShares && isAShare && (isNaN(sharesNum) || sharesNum % 100 !== 0)

  const totalValue = holdings.reduce((sum, h) => {
    const price = realtimePrices[h.code]?.price ?? h.avg_cost
    return sum + h.shares * price
  }, 0)

  const handleAdd = async () => {
    if (!addCode || !addShares || !addCost) {
      setError('请填写代码、股数和成本价')
      return
    }
    if (sharesInvalid) {
      setError('A股股数必须为100的整数倍')
      return
    }
    setError('')
    setSubmitting(true)
    try {
      await createHolding({
        code: addCode,
        name: addName || addCode,
        shares: parseInt(addShares, 10),
        avg_cost: parseFloat(addCost),
        buy_date: addDate,
      })
      setAddCode(''); setAddName(''); setAddShares(''); setAddCost('')
      setShowAdd(false)
      onRefresh?.()
    } catch (e: any) {
      const msg = await e.json?.().catch(() => null)
      setError(msg?.detail || e.message || '添加失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="holdings-panel" style={{ flex: '1 1 40%', minHeight: 0 }}>
      <div className="panel-header">
        <span className="title">持仓列表</span>
        <span className="badge">{holdings.length} 只</span>
        <div className="actions">
          <button className="btn primary" onClick={() => setShowAdd(!showAdd)}>+ 添加持仓</button>
        </div>
      </div>
      {showAdd && (
        <div style={{ padding: '8px 12px', background: 'var(--surface2)', borderBottom: '1px solid var(--border)', display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div className="field">
            <label style={{ fontSize: '0.6rem', color: 'var(--muted)' }}>代码</label>
            <input type="text" placeholder="sh.600519 或 600519" value={addCode} onChange={e => setAddCode(e.target.value)} style={{ width: 120, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 4, color: 'var(--heading)', padding: '4px 8px', fontSize: '0.72rem' }} />
          </div>
          <div className="field">
            <label style={{ fontSize: '0.6rem', color: 'var(--muted)' }}>{nameLoading ? '搜索中...' : '名称'}</label>
            <input type="text" placeholder="自动填充" value={addName} onChange={e => setAddName(e.target.value)} style={{ width: 80, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 4, color: 'var(--heading)', padding: '4px 8px', fontSize: '0.72rem' }} />
          </div>
          <div className="field">
            <label style={{ fontSize: '0.6rem', color: 'var(--muted)' }}>股数{isAShare ? ' (100整倍)' : ''}</label>
            <input type="number" placeholder="100" step={isAShare ? 100 : 1} value={addShares} onChange={e => setAddShares(e.target.value)} style={{ width: 60, background: 'var(--bg)', border: sharesInvalid ? '1px solid var(--up)' : '1px solid var(--border)', borderRadius: 4, color: 'var(--heading)', padding: '4px 8px', fontSize: '0.72rem' }} />
          </div>
          <div className="field">
            <label style={{ fontSize: '0.6rem', color: 'var(--muted)' }}>成本价</label>
            <input type="number" placeholder="0.00" step="0.01" value={addCost} onChange={e => setAddCost(e.target.value)} style={{ width: 80, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 4, color: 'var(--heading)', padding: '4px 8px', fontSize: '0.72rem' }} />
          </div>
          <div className="field">
            <label style={{ fontSize: '0.6rem', color: 'var(--muted)' }}>买入日</label>
            <input type="date" value={addDate} onChange={e => setAddDate(e.target.value)} style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 4, color: 'var(--heading)', padding: '4px 8px', fontSize: '0.72rem' }} />
          </div>
          <button onClick={handleAdd} disabled={submitting} style={{ padding: '5px 16px', borderRadius: 4, border: 'none', background: 'var(--accent)', color: '#000', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer' }}>
            {submitting ? '...' : '添加'}
          </button>
          {error && <span style={{ color: 'var(--up)', fontSize: '0.65rem', alignSelf: 'center' }}>{error}</span>}
        </div>
      )}
      <div style={{ overflowY: 'auto', flex: 1 }}>
        <table className="holdings-table">
          <thead>
            <tr>
              <th>名称/代码</th>
              <th className="r">股数</th>
              <th className="r">成本价</th>
              <th className="r">现价</th>
              <th className="r">市值</th>
              <th className="c">占比</th>
              <th className="r">盈亏</th>
              <th className="c">操作</th>
            </tr>
          </thead>
          <tbody>
            {holdings.map(h => {
              const rt = realtimePrices[h.code]
              const hasRealtime = rt && rt.price > 0
              const price = hasRealtime ? rt!.price : h.avg_cost
              const marketValue = h.shares * price
              const pnl = (price - h.avg_cost) * h.shares
              const pnlPct = h.avg_cost > 0 ? ((price - h.avg_cost) / h.avg_cost) * 100 : 0
              const weight = totalValue > 0 ? (marketValue / totalValue) * 100 : 0
              const isUp = pnl >= 0
              return (
                <tr key={h.id}>
                  <td>
                    <div className="name">{h.name}</div>
                    <div className="code">{h.code}</div>
                  </td>
                  <td className="r">{h.shares}</td>
                  <td className="r">{h.avg_cost.toFixed(2)}</td>
                  <td className="r">
                    {hasRealtime ? price.toFixed(2) : <span style={{ color: 'var(--muted)', fontSize: '0.7rem' }}>--</span>}
                  </td>
                  <td className="r">¥{marketValue.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}</td>
                  <td className="c">
                    <span className="pct-bar">
                      <span className="pct-fill" style={{ width: `${Math.min(weight, 100)}%` }} />
                    </span>
                    {weight.toFixed(0)}%
                  </td>
                  <td className={`r ${isUp ? 'up' : 'down'}`}>
                    {hasRealtime ? (
                      <>
                        {isUp ? '+' : ''}¥{Math.abs(pnl).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}
                        <span className="muted small"> ({isUp ? '+' : ''}{pnlPct.toFixed(1)}%)</span>
                      </>
                    ) : (
                      <span style={{ color: 'var(--muted)', fontSize: '0.7rem' }}>--</span>
                    )}
                  </td>
                  <td className="c">
                    <div className="row-actions">
                      <button onClick={() => onSell(h)}>卖出</button>
                      <button onClick={() => onDelete(h.id)}>删除</button>
                    </div>
                  </td>
                </tr>
              )
            })}
            {holdings.length === 0 && (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: 20, color: 'var(--muted)' }}>
                  暂无持仓，点击「+ 添加持仓」
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
