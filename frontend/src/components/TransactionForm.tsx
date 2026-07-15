// frontend/src/components/TransactionForm.tsx
import { useState, useEffect, useRef } from 'react'
import { stockLookup } from '../api/portfolio'

interface TransactionFormProps {
  onSubmit: (data: {
    code: string; name: string; action: 'buy' | 'sell';
    shares: number; price: number; traded_at: string; note?: string;
  }) => Promise<void>
  prefillCode?: string
  prefillName?: string
}

export default function TransactionForm({ onSubmit, prefillCode, prefillName }: TransactionFormProps) {
  const [code, setCode] = useState(prefillCode || '')
  const [name, setName] = useState(prefillName || '')
  const [action, setAction] = useState<'buy' | 'sell'>('buy')
  const [shares, setShares] = useState('')
  const [price, setPrice] = useState('')
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
  const [note, setNote] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [nameLoading, setNameLoading] = useState(false)
  const lookupTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const isAShare = code.startsWith('sh.') || code.startsWith('sz.')

  // Auto-fill stock name when code changes (debounced)
  useEffect(() => {
    if (lookupTimer.current) clearTimeout(lookupTimer.current)
    if (!code || code.length < 2) return
    if (name && (code.startsWith('sh.') || code.startsWith('sz.') || code.startsWith('us.'))) return
    lookupTimer.current = setTimeout(async () => {
      setNameLoading(true)
      try {
        const data = await stockLookup(code)
        if (data.results.length > 0) {
          const best = data.results[0]
          setCode(best.code)
          setName(best.name)
        }
      } catch { /* ignore */ } finally {
        setNameLoading(false)
      }
    }, 500)
    return () => { if (lookupTimer.current) clearTimeout(lookupTimer.current) }
  }, [code])

  // Auto-fill stock code when name changes (debounced, reverse lookup)
  useEffect(() => {
    if (lookupTimer.current) clearTimeout(lookupTimer.current)
    if (!name || name.trim().length < 2) return
    if (code && (code.startsWith('sh.') || code.startsWith('sz.') || code.startsWith('us.'))) return
    lookupTimer.current = setTimeout(async () => {
      setNameLoading(true)
      try {
        const data = await stockLookup(name.trim())
        if (data.results.length > 0) {
          const best = data.results[0]
          setCode(best.code)
          setName(best.name)
        }
      } catch { /* ignore */ } finally {
        setNameLoading(false)
      }
    }, 500)
    return () => { if (lookupTimer.current) clearTimeout(lookupTimer.current) }
  }, [name])

  const sharesNum = parseInt(shares, 10)
  // Buy: must be 100 multiples. Sell: can be any positive number.
  const sharesInvalid = shares && isAShare && action === 'buy' && (isNaN(sharesNum) || sharesNum % 100 !== 0)

  const handleSubmit = async () => {
    if (!code || !shares || !price) {
      setError('请填写代码、股数和价格')
      return
    }
    if (sharesInvalid) {
      setError('A股买入股数必须为100的整数倍')
      return
    }
    setError('')
    setSubmitting(true)
    try {
      await onSubmit({
        code, name: name || code,
        action,
        shares: parseInt(shares, 10),
        price: parseFloat(price),
        traded_at: `${date}T09:30:00`,
        note: note || undefined,
      })
      setShares('')
      setPrice('')
      setNote('')
    } catch (e: any) {
      setError(e.message || '提交失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="tx-form-panel">
      <div className="panel-header">
        <span className="title">记录交易</span>
      </div>
      <div className="tx-form">
        <div className="field">
          <label>股票代码</label>
          <input type="text" placeholder="sh.600519 或 600519" value={code}
            onChange={e => { setCode(e.target.value); setName('') }} />
        </div>
        <div className="field">
          <label>{nameLoading ? '搜索中...' : '名称'}</label>
          <input type="text" placeholder="自动填充" value={name}
            onChange={e => setName(e.target.value)} style={{ width: 80 }} />
        </div>
        <div className="field">
          <label>操作</label>
          <div className="action-toggle">
            <button className={action === 'buy' ? 'active buy' : 'buy'}
              onClick={() => setAction('buy')}>买入</button>
            <button className={action === 'sell' ? 'active sell' : 'sell'}
              onClick={() => setAction('sell')}>卖出</button>
          </div>
        </div>
        <div className="field">
          <label>股数{isAShare && action === 'buy' ? ' (100整倍)' : ''}</label>
          <input type="number" value={shares} onChange={e => setShares(e.target.value)}
            step={isAShare && action === 'buy' ? 100 : 1}
            style={{ width: 60, border: sharesInvalid ? '1px solid var(--up)' : undefined }} placeholder="100" />
        </div>
        <div className="field">
          <label>价格</label>
          <input type="number" value={price} onChange={e => setPrice(e.target.value)}
            style={{ width: 80 }} placeholder="0.00" step="0.01" />
        </div>
        <div className="field">
          <label>日期</label>
          <input type="date" value={date} onChange={e => setDate(e.target.value)} />
        </div>
        <div className="field">
          <label>备注</label>
          <input type="text" placeholder="可选" value={note}
            onChange={e => setNote(e.target.value)} style={{ width: 100 }} />
        </div>
        <button className="submit-btn" onClick={handleSubmit} disabled={submitting}>
          {submitting ? '提交中...' : '提交'}
        </button>
        {error && <span style={{ color: 'var(--up)', fontSize: '0.65rem' }}>{error}</span>}
      </div>
    </div>
  )
}
