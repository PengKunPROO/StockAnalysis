// frontend/src/components/TransactionHistory.tsx
import { useState, useEffect, useCallback } from 'react'
import { getTransactions, deleteTransaction } from '../api/portfolio'
import type { Transaction } from '../api/portfolio'

interface TransactionHistoryProps {
  refreshKey: number
  onTransactionDeleted: () => void
}

const PAGE_SIZE = 7

export default function TransactionHistory({ refreshKey, onTransactionDeleted }: TransactionHistoryProps) {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [page, setPage] = useState(1)
  const [filter, setFilter] = useState('')
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getTransactions(page, PAGE_SIZE, filter)
      setTransactions(data.transactions)
      setTotal(data.total)
      setTotalPages(data.total_pages)
    } catch {
      setTransactions([])
    } finally {
      setLoading(false)
    }
  }, [page, filter])

  useEffect(() => { load() }, [load, refreshKey])

  const handleDelete = async (id: number) => {
    await deleteTransaction(id)
    onTransactionDeleted()
  }

  return (
    <div className="tx-history-panel" style={{ flex: '1 1 30%', minHeight: 0, maxHeight: 'none' }}>
      <div className="panel-header">
        <span className="title">交易记录</span>
        <span className="badge">共 {total} 笔</span>
        <div className="actions">
          <select value={filter} onChange={e => { setFilter(e.target.value); setPage(1) }}
            style={{ padding: '2px 6px', borderRadius: 3, border: '1px solid var(--border)', background: 'var(--surface2)', color: 'var(--heading)', fontSize: '0.62rem' }}>
            <option value="">全部</option>
            <option value="buy">买入</option>
            <option value="sell">卖出</option>
          </select>
        </div>
      </div>
      <div className="tx-list">
        {loading && <div style={{ padding: 12, color: 'var(--muted)', fontSize: '0.65rem' }}>加载中...</div>}
        {!loading && transactions.length === 0 && (
          <div style={{ padding: 12, color: 'var(--muted)', fontSize: '0.65rem' }}>暂无交易记录</div>
        )}
        {transactions.map(tx => {
          const dateStr = tx.traded_at?.slice(5, 10) || '--'
          return (
            <div className="tx-row" key={tx.id}>
              <span className="tx-date">{dateStr}</span>
              <span className={`tx-action ${tx.action}`}>{tx.action === 'buy' ? '买' : '卖'}</span>
              <span className="tx-name">{tx.name}</span>
              <span className="tx-code">{tx.code}</span>
              <span className="tx-shares">{tx.shares}股</span>
              <span className="tx-price">@{tx.price.toFixed(2)}</span>
              <span className="tx-amount">¥{tx.amount.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}</span>
              {tx.note && <span className="tx-note">{tx.note}</span>}
              <button className="tx-del" onClick={() => handleDelete(tx.id)}>×</button>
            </div>
          )
        })}
      </div>
      <div className="tx-pagination">
        <span className="page-info">第 {page}/{totalPages} 页 · 每页 {PAGE_SIZE} 笔</span>
        <div className="page-controls">
          <button disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))}>‹ 上一页</button>
          {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => i + 1).map(p => (
            <button key={p} className={p === page ? 'active' : ''} onClick={() => setPage(p)}>{p}</button>
          ))}
          <button disabled={page >= totalPages} onClick={() => setPage(p => Math.min(totalPages, p + 1))}>下一页 ›</button>
        </div>
      </div>
    </div>
  )
}
