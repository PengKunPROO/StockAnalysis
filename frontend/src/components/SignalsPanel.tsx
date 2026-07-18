import { useState, useCallback, useEffect } from 'react'
import { useApp } from '../contexts/AppContext'
import { streamSignalsAI } from '../api/signals'

export default function SignalsPanel() {
  const { state, dispatch } = useApp()
  const data = state.signals
  const code = state.currentStock?.code
  const [tab, setTab] = useState<'rules' | 'ai'>('rules')

  const [aiText, setAiText] = useState('')
  const [aiReasoning, setAiReasoning] = useState('')
  const [aiLoading, setAiLoading] = useState(false)
  const [aiError, setAiError] = useState('')

  // Reset AI state when stock changes
  useEffect(() => {
    setAiText(''); setAiReasoning(''); setAiError(''); setAiLoading(false)
  }, [code])

  const runAi = useCallback(async () => {
    if (!code || aiLoading) return
    setAiText(''); setAiReasoning(''); setAiError(''); setAiLoading(true)
    await streamSignalsAI(code, {
      onSignals: (p) => dispatch({ type: 'SET_SIGNALS', signals: p }),
      onReasoning: (chunk) => setAiReasoning(prev => prev + chunk),
      onContent: (chunk) => setAiText(prev => prev + chunk),
      onError: (msg) => setAiError(msg),
      onDone: () => setAiLoading(false),
    })
  }, [code, aiLoading, dispatch])

  const score = data?.score
  const signals = data?.active_signals || []
  const levels = data?.key_levels || []
  const risk = data?.risk

  return (
    <div className="signals-panel">
      <div className="signals-header">
        <span className="title">操作建议</span>
        <div className="signals-tabs">
          <button className={tab === 'rules' ? 'active' : ''} onClick={() => setTab('rules')}>规则信号</button>
          <button className={tab === 'ai' ? 'active' : ''} onClick={() => setTab('ai')}>AI解读</button>
        </div>
        <span className="hint">{tab === 'rules' ? '实时计算 · 不依赖LLM' : '▸ SSE流式'}</span>
      </div>

      {!data && <div className="signals-loading">{code ? '计算信号中...' : '选择股票后显示信号'}</div>}

      {data && tab === 'rules' && (
        <div className="signals-body">
          <div className="signals-col">
            <div className="col-title">活跃信号</div>
            <div className="signal-list">
              {signals.length === 0 && <div className="empty">无活跃信号</div>}
              {signals.map((s, i) => {
                const c = s.direction === 'bull' ? 'var(--accent)' : 'var(--up)'
                return (
                  <div key={i} className="signal-item" style={{ borderColor: c, background: `${c}1a` }}>
                    <span className="arrow" style={{ color: c }}>{s.direction === 'bull' ? '▲' : '▼'}</span>
                    <div className="info">
                      <span className="name" style={{ color: c }}>{s.name}</span>
                      <span className="detail">{s.detail}</span>
                    </div>
                    <span className="badge" style={{ background: `${c}33`, color: c }}>{s.strength}</span>
                  </div>
                )
              })}
            </div>

            {score && (
              <div className="signal-score">
                <div className="col-title">信号强度</div>
                <div className="score-bar-wrap">
                  <span className="end-label">空头</span>
                  <div className="score-bar">
                    <div className="score-marker" style={{ left: `${score.pct}%` }} />
                  </div>
                  <span className="end-label">多头</span>
                </div>
                <div className="score-label" style={{ color: score.pct >= 65 ? 'var(--accent)' : score.pct <= 35 ? 'var(--up)' : 'var(--gold)' }}>
                  {score.label} ({score.pct}%)
                </div>
              </div>
            )}
          </div>

          <div className="signals-col">
            <div className="col-title">关键价位</div>
            <div className="level-list">
              {levels.length === 0 && <div className="empty">无关键价位</div>}
              {levels.map((lvl, i) => {
                const c = lvl.type === '阻力' ? 'var(--down)' : lvl.type === '斐波' ? 'var(--gold)' : 'var(--up)'
                return (
                  <div key={i} className="level-item" style={{ borderColor: `${c}33`, background: `${c}14` }}>
                    <span className="lvl-price" style={{ color: c }}>{lvl.type} {lvl.price}</span>
                    <span className="lvl-src">{lvl.source}</span>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="signals-col">
            <div className="col-title">风险管理</div>
            <div className="risk-list">
              {risk ? (
                <>
                  <div className="risk-row"><span>ATR(14)</span><b>{risk.atr}</b></div>
                  <div className="risk-row"><span className="up">止损价</span><b className="up">{risk.stop_loss} ({risk.stop_loss_pct}%)</b></div>
                  <div className="risk-row"><span className="down">止盈价</span><b className="down">{risk.take_profit} (+{risk.take_profit_pct}%)</b></div>
                  <div className="risk-row"><span className="gold">凯利仓位</span><b className="gold">{risk.kelly_pct}%</b></div>
                  <div className="risk-row"><span>盈亏比</span><b className="accent">{risk.risk_reward_ratio}</b></div>
                </>
              ) : <div className="empty">数据不足</div>}
            </div>
          </div>
        </div>
      )}

      {data && tab === 'ai' && (
        <div className="ai-body">
          {aiText === '' && aiReasoning === '' && !aiLoading && !aiError && (
            <button className="ai-run-btn" onClick={runAi}>▸ 生成AI解读</button>
          )}
          {aiLoading && aiText === '' && aiReasoning === '' && <div className="signals-loading">AI 分析中...</div>}
          {aiError && <div className="signals-loading" style={{ color: 'var(--up)' }}>{aiError}</div>}
          {aiReasoning && <pre className="ai-reasoning">💭 思考过程: {aiReasoning}{aiLoading && aiText === '' ? '▍' : ''}</pre>}
          {aiText && <pre className="ai-text">{aiText}{aiLoading && '▍'}</pre>}
          <div className="ai-disclaimer">⚠ 以上为AI分析参考，不构成投资建议。市场有风险，请结合自身情况决策。</div>
        </div>
      )}

      {data?.summary && tab === 'rules' && (
        <div className="signals-summary">
          <span className="label">📊 总结：</span>
          <span>{data.summary}</span>
        </div>
      )}
    </div>
  )
}
