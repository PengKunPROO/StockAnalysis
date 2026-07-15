// frontend/src/components/PortfolioView.tsx
import { useState, useEffect, useCallback, useRef } from 'react'
import { getHoldings, deleteHolding, createTransaction, getReport, generateReport, getHoldingsRealtime, stockLookup } from '../api/portfolio'
import type { Holding, ReportDetail } from '../api/portfolio'
import PortfolioDashboard from './PortfolioDashboard'
import HoldingsTable from './HoldingsTable'
import TransactionForm from './TransactionForm'
import TransactionHistory from './TransactionHistory'
import DailyReportView from './DailyReportView'
import ResizableSplitter from './ResizableSplitter'

export default function PortfolioView() {
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [report, setReport] = useState<ReportDetail | null>(null)
  const [reportDate, setReportDate] = useState(new Date().toISOString().slice(0, 10))
  const [generating, setGenerating] = useState(false)
  const [txRefreshKey, setTxRefreshKey] = useState(0)
  const [leftWidth, setLeftWidth] = useState(55) // percentage
  const leftRef = useRef<HTMLDivElement>(null)
  const bodyRef = useRef<HTMLDivElement>(null)

  const [realtimePrices, setRealtimePrices] = useState<Record<string, { price: number; change_pct: number }>>({})
  const [holdingsError, setHoldingsError] = useState<string | null>(null)

  const loadRealtimePrices = useCallback(async () => {
    try {
      const data = await getHoldingsRealtime()
      setRealtimePrices(data.prices || {})
    } catch (e) {
      // Realtime fetch failed (e.g. non-trading hours, network) — leave prices empty
      // so consumers can show "--" instead of falling back to avg_cost as current price.
      console.warn('Failed to load realtime prices:', e)
      setRealtimePrices({})
    }
  }, [])

  // Reload realtime prices whenever holdings change OR after a transaction is added/removed.
  // Depending on `holdings` alone is insufficient when length is unchanged (e.g. avg_cost
  // updates after a buy of an existing code); txRefreshKey covers that case explicitly.
  useEffect(() => { loadRealtimePrices() }, [holdings, txRefreshKey, loadRealtimePrices])

  const loadHoldings = useCallback(async () => {
    try {
      const data = await getHoldings()
      setHoldings(data.holdings || [])
      setHoldingsError(null)
    } catch (e) {
      console.error('Failed to load holdings:', e)
      setHoldings([])
      setHoldingsError('持仓加载失败，请稍后重试')
    }
  }, [])

  const loadReport = useCallback(async (date: string) => {
    try {
      const r = await getReport(date)
      setReport(r)
    } catch {
      setReport(null)
    }
  }, [])

  useEffect(() => { loadHoldings() }, [loadHoldings])
  useEffect(() => { loadReport(reportDate) }, [loadReport, reportDate])

  // Reload holdings (and dependent realtime prices via the effect above) after a transaction
  // is created or deleted. Await so callers know the refresh is complete.
  const onTransactionChange = useCallback(async () => {
    setTxRefreshKey(k => k + 1)
    await loadHoldings()
    // Explicitly refresh realtime prices too; the holdings effect covers the common case
    // but this guards against the same-length holdings edge case.
    await loadRealtimePrices()
  }, [loadHoldings, loadRealtimePrices])

  const handleDeleteHolding = async (id: number) => {
    try {
      await deleteHolding(id)
      await loadHoldings()
      await loadRealtimePrices()
    } catch (e) {
      console.error('Failed to delete holding:', e)
    }
  }

  const handleSell = (holding: Holding) => {
    // This would typically open a modal or prefill the transaction form
    // For now, we just scroll to the form - the user can manually enter sell info
    console.log('Sell holding:', holding)
  }

  const handleCreateTransaction = async (data: {
    code: string; name: string; action: 'buy' | 'sell';
    shares: number; price: number; traded_at: string; note?: string;
  }) => {
    try {
      await createTransaction(data)
      // Await the full refresh so the dashboard/holdings reflect the new transaction
      // before this promise resolves (TransactionForm relies on this for feedback).
      await onTransactionChange()
    } catch (e) {
      console.error('Transaction submit failed:', e)
      throw e
    }
  }

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      await generateReport()
      const startTime = Date.now()
      const poll = async () => {
        if (Date.now() - startTime > 300000) {
          setGenerating(false)
          return
        }
        try {
          const r = await getReport(reportDate)
          if (r) {
            setReport(r)
            if (r.status === 'completed' || r.status === 'failed') {
              setGenerating(false)
              return
            }
          }
        } catch { /* report not yet created, will retry */ }
        setTimeout(poll, 10000)
      }
      setTimeout(poll, 5000)
    } catch {
      setGenerating(false)
    }
  }

  // Resizable splitter handlers
  const handleHorizontalResize = useCallback((delta: number) => {
    if (!bodyRef.current) return
    const containerWidth = bodyRef.current.offsetWidth
    const deltaPct = (delta / containerWidth) * 100
    setLeftWidth(w => Math.max(30, Math.min(70, w + deltaPct)))
  }, [])

  // Calculate dashboard metrics.
  // When realtime prices are unavailable (non-trading hours, API down), we must NOT
  // fall back to avg_cost for "current price" — that makes totalMarketValue === totalCost
  // and PnL appear as 0, which looks like a data bug. Instead, track whether any realtime
  // data is available; if not, the dashboard shows the cost-based value with no PnL claim.
  const hasRealtime = holdings.length > 0 && holdings.some(h => {
    const rt = realtimePrices[h.code]
    return rt && rt.price > 0
  })
  const totalMarketValue = holdings.reduce((sum, h) => {
    const rt = realtimePrices[h.code]
    const price = rt && rt.price > 0 ? rt.price : h.avg_cost
    return sum + h.shares * price
  }, 0)
  const totalCost = holdings.reduce((sum, h) => sum + h.shares * h.avg_cost, 0)
  // Only claim a PnL when we actually have realtime prices; otherwise show 0 PnL
  // (the dashboard distinguishes "no realtime data" via the hasRealtime flag below).
  const totalPnl = hasRealtime ? totalMarketValue - totalCost : 0
  const pnlPct = hasRealtime && totalCost > 0 ? (totalPnl / totalCost) * 100 : 0
  const todayChange = 0 // Would come from realtime data
  const todayChangePct = 0

  return (
    <>
      <div className="pf-toolbar">
        <div className="report-date">
          <label>报告日期</label>
          <input type="date" value={reportDate} onChange={e => setReportDate(e.target.value)} />
        </div>
        <button className="generate-btn" onClick={handleGenerate} disabled={generating}>
          {generating ? '⏳ 生成中...' : '🔄 生成今日报告'}
        </button>
      </div>

      <div className="content" style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, padding: '12px 16px', gap: 12 }}>
        {/* Status banners */}
        {holdingsError && (
          <div style={{ padding: '6px 12px', background: 'var(--surface2)', border: '1px solid var(--down)', borderRadius: 6, color: 'var(--down)', fontSize: '0.75rem' }}>
            ⚠ {holdingsError}
          </div>
        )}
        {!holdingsError && holdings.length > 0 && !hasRealtime && (
          <div style={{ padding: '6px 12px', background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--muted)', fontSize: '0.75rem' }}>
            ⓘ 实时行情暂不可用（非交易时段或接口异常），市值按成本价估算，盈亏显示为 -- 
          </div>
        )}
        {/* Dashboard Cards */}
        <PortfolioDashboard
          holdings={holdings}
          totalMarketValue={totalMarketValue}
          totalCost={totalCost}
          totalPnl={totalPnl}
          pnlPct={pnlPct}
          todayChange={todayChange}
          todayChangePct={todayChangePct}
        />

        {/* Two-column body with resizable splitter */}
        <div className="pf-body" ref={bodyRef}>
          {/* Left: Holdings + Tx Form + Tx History */}
          <div className="pf-left" ref={leftRef} style={{ width: `${leftWidth}%` }}>
            <HoldingsTable
              holdings={holdings}
              realtimePrices={realtimePrices}
              onDelete={handleDeleteHolding}
              onSell={handleSell}
              onRefresh={loadHoldings}
            />
            <ResizableSplitter direction="vertical" onResize={() => {}} />
            <TransactionForm onSubmit={handleCreateTransaction} />
            <ResizableSplitter direction="vertical" onResize={() => {}} />
            <TransactionHistory
              refreshKey={txRefreshKey}
              onTransactionDeleted={onTransactionChange}
            />
          </div>

          <ResizableSplitter direction="horizontal" onResize={handleHorizontalResize} />

          {/* Right: Daily Report */}
          <div className="pf-right">
            <DailyReportView
              report={report}
              generating={generating}
              onGenerate={handleGenerate}
            />
          </div>
        </div>
      </div>
    </>
  )
}
