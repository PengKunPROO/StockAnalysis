// frontend/src/components/HoldingsTable.tsx
import type { Holding } from '../api/portfolio'

interface HoldingsTableProps {
  holdings: Holding[]
  realtimePrices: Record<string, { price: number; change_pct: number }>
  onDelete: (id: number) => void
  onSell: (holding: Holding) => void
}

export default function HoldingsTable({ holdings, realtimePrices, onDelete, onSell }: HoldingsTableProps) {
  const totalValue = holdings.reduce((sum, h) => {
    const price = realtimePrices[h.code]?.price ?? h.avg_cost
    return sum + h.shares * price
  }, 0)

  return (
    <div className="holdings-panel" style={{ flex: '1 1 40%', minHeight: 0 }}>
      <div className="panel-header">
        <span className="title">持仓列表</span>
        <span className="badge">{holdings.length} 只</span>
        <div className="actions">
          <button className="btn primary">+ 添加持仓</button>
        </div>
      </div>
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
              const price = rt?.price ?? h.avg_cost
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
                  <td className="r">{price.toFixed(2)}</td>
                  <td className="r">¥{marketValue.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}</td>
                  <td className="c">
                    <span className="pct-bar">
                      <span className="pct-fill" style={{ width: `${Math.min(weight, 100)}%` }} />
                    </span>
                    {weight.toFixed(0)}%
                  </td>
                  <td className={`r ${isUp ? 'up' : 'down'}`}>
                    {isUp ? '+' : ''}¥{Math.abs(pnl).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}
                    <span className="muted small"> ({isUp ? '+' : ''}{pnlPct.toFixed(1)}%)</span>
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
                  暂无持仓，请通过交易记录添加
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
