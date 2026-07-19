import { useState, useRef, useEffect, memo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useApp } from '../contexts/AppContext'
import { aiScan } from '../api/screener'
import type { SkillMeta } from '../types'

const MemoMarkdown = memo(function MD({ content }: { content: string }) {
  return (
    <div className="msg-body">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
        table: ({ children }) => <table className="md-table">{children}</table>,
        th: ({ children }) => <th>{children}</th>,
        td: ({ children }) => <td>{children}</td>,
        code: ({ children, className }) => {
          const isBlock = className?.includes('language-')
          return isBlock ? <pre className="md-code-block"><code>{children}</code></pre> : <code className="md-inline-code">{children}</code>
        },
        blockquote: ({ children }) => <blockquote className="md-quote">{children}</blockquote>,
        ul: ({ children }) => <ul className="md-ul">{children}</ul>,
        ol: ({ children }) => <ol className="md-ol">{children}</ol>,
        li: ({ children }) => <li className="md-li">{children}</li>,
        h1: ({ children }) => <h2 className="md-h1">{children}</h2>,
        h2: ({ children }) => <h3 className="md-h2">{children}</h3>,
        h3: ({ children }) => <h4 className="md-h3">{children}</h4>,
        p: ({ children }) => <p className="md-p">{children}</p>,
        strong: ({ children }) => <strong className="md-strong">{children}</strong>,
      }}>
        {content}
      </ReactMarkdown>
    </div>
  )
})

function SkillChip({ skills, skill, useSkill, onToggle, onPick }: {
  skills: SkillMeta[]
  skill: string
  useSkill: boolean
  onToggle: () => void
  onPick: (name: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const ref = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h); return () => document.removeEventListener('mousedown', h)
  }, [])

  const filtered = query.trim()
    ? skills.filter(s => s.name.toLowerCase().includes(query.toLowerCase()) || s.description?.toLowerCase().includes(query.toLowerCase()))
    : skills

  return (
    <div ref={ref} style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
      <div className={`skill-chip ${useSkill ? 'active' : ''}`} onClick={(e) => { e.stopPropagation(); onToggle() }}>
        <div className="skill-chip-dot" />
        <span className={`skill-chip-name ${!skill ? 'unset' : ''}`} onClick={(e) => { e.stopPropagation(); setOpen(!open); setTimeout(() => inputRef.current?.focus(), 50) }}>
          {skill || '选股 Skill'}
        </span>
        <span className="skill-chip-caret" onClick={(e) => { e.stopPropagation(); setOpen(!open); setTimeout(() => inputRef.current?.focus(), 50) }}>▼</span>
      </div>
      {open && (
        <div className="skill-dropdown open">
          <div className="skill-search-wrap">
            <span className="skill-search-icon">🔍</span>
            <input ref={inputRef} className="skill-search" value={query} onChange={e => setQuery(e.target.value)}
              placeholder="搜索 Skill..." onKeyDown={e => { if (e.key === 'Escape') setOpen(false) }} />
          </div>
          <div className="skill-list">
            {filtered.map(s => (
              <div key={s.name} className={`skill-opt ${s.name === skill ? 'sel' : ''}`} onClick={() => { onPick(s.name); setOpen(false); setQuery('') }}>
                <div><span className="sn">{s.name}</span></div>
                {s.description && <div className="sd">{s.description.slice(0, 60)}{s.description.length > 60 ? '…' : ''}</div>}
              </div>
            ))}
            {filtered.length === 0 && <div className="skill-opt" style={{ color: 'var(--muted)', cursor: 'default' }}>无匹配结果</div>}
          </div>
        </div>
      )}
    </div>
  )
}

export default function AIScreenerPanel() {
  const { state } = useApp()
  const [input, setInput] = useState('')
  const [result, setResult] = useState('')
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState('')
  const [skill, setSkill] = useState('')
  const [useSkill, setUseSkill] = useState(true)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [result])

  const run = async () => {
    if (!input.trim() || loading) return
    const text = input.trim()
    setLoading(true); setResult(''); setStatus('agent_starting')
    let full = ''
    await aiScan({
      message: text, skill, use_skill: useSkill,
      stock_codes: state.currentStock ? [{ code: state.currentStock.code, name: state.currentStock.name }] : [],
    }, {
      onStatus: s => setStatus(s),
      onContent: c => { full += c; setResult(full); setStatus('') },
      onLog: () => { if (!status) setStatus('fetching_data') },
      onDone: () => { setLoading(false); setStatus('') },
      onError: e => { setResult(`Error: ${e}`); setLoading(false); setStatus('') },
    })
  }

  const statusText: Record<string, string> = { agent_starting: 'Agent 启动中...', fetching_data: '获取数据中...' }

  return (
    <div className="ai-screener-panel">
      <div className="ai-screener-header">
        <span className="title">🔍 AI 选股</span>
        <span style={{ flex: 1 }} />
        <SkillChip
          skills={state.skills}
          skill={skill}
          useSkill={useSkill}
          onToggle={() => setUseSkill(v => !v)}
          onPick={setSkill}
        />
      </div>
      <div className="ai-screener-input">
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); run() } }}
          placeholder='输入选股意图，如"找超跌反弹股，基本面要好"...'
          disabled={loading}
          rows={2}
        />
        <button onClick={run} disabled={loading || !input.trim()}>
          {loading ? '分析中...' : '开始选股'}
        </button>
      </div>
      {(loading || status) && (
        <div className="chat-status">
          <span className="dot" /> {statusText[status] || status || '处理中...'}
        </div>
      )}
      {result && (
        <div className="ai-screener-result">
          <MemoMarkdown content={result} />
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  )
}
