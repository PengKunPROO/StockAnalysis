// frontend/src/components/TransactionForm.tsx
import { useState } from 'react'

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

  const handleSubmit = async () => {
    if (!code || !shares || !price) return
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
          <input type="text" placeholder="sh.600519" value={code}
            onChange={e => setCode(e.target.value)} />
        </div>
        <div className="field">
          <label>名称</label>
          <input type="text" placeholder="名称" value={name}
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
          <label>股数</label>
          <input type="number" value={shares} onChange={e => setShares(e.target.value)}
            style={{ width: 60 }} placeholder="100" />
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
      </div>
    </div>
  )
}
