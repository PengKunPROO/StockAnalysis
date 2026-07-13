// frontend/src/components/PortfolioView.tsx
import { useState, useEffect, useCallback, useRef } from 'react'
import { getHoldings, deleteHolding, createTransaction, getReport, generateReport } from '../api/portfolio'
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

  // Realtime prices placeholder (in real app, would fetch from API)
  const [realtimePrices] = useState<Record<string, { price: number; change_pct: number }>>({})

  const loadHoldings = useCallback(async () => {
    try {
      const data = await getHoldings()
      setHoldings(data.holdings || [])
    } catch {
      setHoldings([])
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

  // Reload holdings when transactions change
  const onTransactionChange = useCallback(() => {
    setTxRefreshKey(k => k + 1)
    loadHoldings()
  }, [loadHoldings])

  const handleDeleteHolding = async (id: number) => {
    await deleteHolding(id)
    loadHoldings()
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
    await createTransaction(data)
    onTransactionChange()
  }

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      await generateReport()
      // Poll for report after a delay
      setTimeout(async () => {
        await loadReport(reportDate)
        setGenerating(false)
      }, 5000)
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

  // Calculate dashboard metrics
  const totalMarketValue = holdings.reduce((sum, h) => {
    const price = realtimePrices[h.code]?.price ?? h.avg_cost
    return sum + h.shares * price
  }, 0)
  const totalCost = holdings.reduce((sum, h) => sum + h.shares * h.avg_cost, 0)
  const totalPnl = totalMarketValue - totalCost
  const pnlPct = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0
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
