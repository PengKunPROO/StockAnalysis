// frontend/src/components/DailyReportView.tsx
import { useState } from 'react'
import type { ReportDetail, ReportContextRaw } from '../api/portfolio'

interface DailyReportViewProps {
  report: ReportDetail | null
  generating: boolean
  onGenerate: () => void
}

function safeParse(str: string | null | undefined): any {
  if (!str) return {}
  try { return JSON.parse(str) } catch { return {} }
}

const ADVICE_LABELS: Record<string, string> = {
  buy: '加仓', sell: '减仓', hold: '持有', watch: '观望', stop: '止损',
}

const PRIORITY_MAP: Record<number, 'high' | 'medium' | 'low'> = {
  1: 'high', 2: 'medium', 3: 'low',
}

export default function DailyReportView({ report, generating, onGenerate }: DailyReportViewProps) {
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set())

  const toggleCard = (code: string) => {
    setExpandedCards(prev => {
      const next = new Set(prev)
      if (next.has(code)) next.delete(code)
      else next.add(code)
      return next
    })
  }

  if (generating) {
    return (
      <div className="report-panel">
        <div className="panel-header">
          <span className="title">每日操作指导</span>
        </div>
        <div className="report-status">
          <span className="dot" />
          <span className="label">报告生成中...</span>
          <span className="meta">AI 分析进行中，请稍候</span>
        </div>
        <div className="report-body">
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--muted)' }}>⏳ 正在生成每日分析报告...</div>
        </div>
      </div>
    )
  }

  if (!report) {
    return (
      <div className="report-panel">
        <div className="panel-header">
          <span className="title">每日操作指导</span>
          <div className="actions">
            <button className="btn primary" onClick={onGenerate}>🔄 生成报告</button>
          </div>
        </div>
        <div className="report-body">
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--muted)' }}>
            <div style={{ fontSize: '2rem', marginBottom: 8 }}>📋</div>
            尚未生成今日报告
            <div style={{ fontSize: '0.65rem', marginTop: 4 }}>点击「生成报告」启动 AI 分析</div>
          </div>
        </div>
      </div>
    )
  }

  const portfolioSection = report.sections.find(s => s.section_type === 'portfolio_analysis')
  const stockSections = report.sections.filter(s => s.section_type === 'stock_analysis')
  const actionSection = report.sections.find(s => s.section_type === 'action_plan')
  const portfolioData = safeParse(portfolioSection?.content)
  const stockData = stockSections.map(s => ({ ...safeParse(s.content), stock_code: s.stock_code, status: s.status }))
  const contexts = report.contexts || []

  return (
    <div className="report-panel">
      <div className="panel-header">
        <span className="title">每日操作指导</span>
        <span className="badge">{report.report_date}</span>
        <div className="actions">
          <button className="btn primary" onClick={onGenerate}>🔄 重新生成</button>
        </div>
      </div>

      {/* Status bar */}
      <div className="report-status">
        <span className={`dot ${report.status === 'completed' ? 'completed' : report.status === 'failed' ? 'failed' : ''}`} />
        <span className="label">
          {report.status === 'completed' ? '报告已生成' : report.status === 'running' ? '生成中...' : report.status === 'failed' ? '生成失败' : '待生成'}
        </span>
        <span className="meta">
          {report.status === 'completed'
            ? `${stockData.length}/${stockData.length} 股分析完成`
            : report.status}
        </span>
      </div>

      <div className="report-body">
        {/* Portfolio Analysis Section */}
        <div className="report-section">
          <div className="section-title"><span className="icon">📊</span>组合分析</div>
          <div className="stat-grid">
            <div className="stat-item">
              <div className="stat-label">总市值</div>
              <div className="stat-value">{report.total_market_value != null ? `¥${(report.total_market_value / 10000).toFixed(2)}万` : '--'}</div>
            </div>
            <div className="stat-item">
              <div className="stat-label">总盈亏</div>
              <div className={`stat-value ${(report.total_pnl ?? 0) >= 0 ? 'up' : 'down'}`}>
                {(report.total_pnl ?? 0) >= 0 ? '+' : ''}¥{Math.abs(report.total_pnl ?? 0).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}
              </div>
            </div>
            <div className="stat-item">
              <div className="stat-label">盈亏比</div>
              <div className="stat-value gold">{(report.pnl_pct ?? 0).toFixed(2)}%</div>
            </div>
            <div className="stat-item">
              <div className="stat-label">持仓数</div>
              <div className="stat-value">{stockData.length}</div>
            </div>
          </div>
          {/* Industry exposure bars if available */}
          {portfolioData?.position_weights && Array.isArray(portfolioData.position_weights) && (
            <div className="industry-bars">
              {portfolioData.position_weights.slice(0, 5).map((w: any, i: number) => (
                <div className="ind-bar-row" key={w.code || i}>
                  <span className="ind-name">{w.name || w.code}</span>
                  <div className="ind-bar-track">
                    <div className="ind-bar-fill" style={{
                      width: `${Math.min(w.weight, 100)}%`,
                      background: DONUT_FILL_COLORS[i % DONUT_FILL_COLORS.length],
                    }} />
                  </div>
                  <span className="ind-pct">{(w.weight || 0).toFixed(1)}%</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Stock Analysis Cards */}
        {stockData.length > 0 && (
          <div className="report-section">
            <div className="section-title"><span className="icon">🎯</span>逐股分析</div>
            <div className="stock-cards">
              {stockData.map((sa) => {
                const code = sa.stock_code || sa.code || ''
                const expanded = expandedCards.has(code)
                const advice = sa.advice || 'hold'
                return (
                  <div className={`stock-card ${expanded ? 'expanded' : ''}`} key={code}>
                    <div className="stock-card-header" onClick={() => toggleCard(code)}>
                      <span className="sc-name">{sa.name || code}</span>
                      <span className="sc-code">{code}</span>
                      <span className={`advice-tag ${advice}`}>
                        {ADVICE_LABELS[advice] || advice}
                      </span>
                      <span className="sc-weight">{sa.status === 'failed' ? '分析失败' : '分析完成'}</span>
                    </div>
                    <div className="stock-card-body">
                      {sa.stop_loss != null || sa.target != null || sa.buy_range != null ? (
                        <div className="sc-levels">
                          {sa.buy_range && (
                            <div className="sc-level">
                              <span className="lbl">买入区间</span>
                              <span className="val down">{sa.buy_range}</span>
                            </div>
                          )}
                          {sa.stop_loss != null && (
                            <div className="sc-level">
                              <span className="lbl">止损价</span>
                              <span className="val up">{sa.stop_loss}</span>
                            </div>
                          )}
                          {sa.target != null && (
                            <div className="sc-level">
                              <span className="lbl">目标价</span>
                              <span className="val up">{sa.target}</span>
                            </div>
                          )}
                          {sa.current_price != null && (
                            <div className="sc-level">
                              <span className="lbl">现价</span>
                              <span className="val">{sa.current_price}</span>
                            </div>
                          )}
                        </div>
                      ) : null}
                      <div className="sc-analysis">{sa.analysis || '无分析内容'}</div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Action Plan */}
        {actionSection?.content && (
          <div className="report-section">
            <div className="section-title"><span className="icon">📋</span>今日行动计划</div>
            <div className="action-plan">
              <div className="action-item">
                <span className="priority high">!</span>
                <span className="desc">{renderActionText(actionSection.content)}</span>
              </div>
            </div>
          </div>
        )}

        {/* Cross-day Tracking */}
        {contexts.length > 0 && (
          <div className="report-section">
            <div className="section-title"><span className="icon">📅</span>前日建议追踪</div>
            <div className="tracking-list">
              {contexts.map((ctx: ReportContextRaw) => (
                <div className="track-row" key={ctx.id}>
                  <span className="t-stock">{ctx.stock_code}</span>
                  <span className="t-advice">
                    {ADVICE_LABELS[ctx.advice_type] || ctx.advice_type}
                    {ctx.key_price != null ? ` · 关键价 ${ctx.key_price}` : ''}
                    {ctx.advice_text ? ` · ${ctx.advice_text.slice(0, 80)}` : ''}
                  </span>
                  <span className={`t-result ${ctx.executed ? (ctx.execution_result?.includes('profit') || ctx.execution_result?.includes('赢') ? 'executed-profit' : 'executed-loss') : 'not-executed'}`}>
                    {ctx.executed ? (ctx.execution_result || '已执行') : '未执行'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Summary */}
        {report.summary && (
          <div className="report-summary">
            {report.summary}
          </div>
        )}

        {/* Disclaimer */}
        <div className="pf-disclaimer">
          ⚠️ 以上分析由 AI 基于技术指标、基本面数据和公开新闻生成，仅供参考，不构成投资建议。投资有风险，决策需谨慎。
        </div>
      </div>
    </div>
  )
}

const DONUT_FILL_COLORS = ['var(--accent)', 'var(--up)', 'var(--gold)', 'var(--down)', 'var(--muted)']

function renderActionText(content: string): React.ReactNode {
  // The action_plan section content is the summary text (from generate_summary)
  // Try to parse as JSON array of action items; fallback to plain text
  try {
    const parsed = JSON.parse(content)
    if (Array.isArray(parsed)) {
      return parsed.map((item: any, i: number) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0', borderBottom: '1px solid var(--border-light)' }}>
          <span className={`priority ${PRIORITY_MAP[i + 1] || 'low'}`}>{i + 1}</span>
          <span className="desc">{item.action || item.desc || JSON.stringify(item)}</span>
        </div>
      ))
    }
  } catch {
    // Not JSON, render as text
  }
  return content
}
