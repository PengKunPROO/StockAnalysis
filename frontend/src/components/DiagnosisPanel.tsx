import { useState, useRef, useEffect, memo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useApp } from '../contexts/AppContext'
import { chatStream } from '../api/diagnosis'
import type { ChatMessage as ChatMsg, SkillMeta } from '../types'

function MarkdownContent({ content }: { content: string }) {
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
        h4: ({ children }) => <h5 className="md-h4">{children}</h5>,
        p: ({ children }) => <p className="md-p">{children}</p>,
        strong: ({ children }) => <strong className="md-strong">{children}</strong>,
        a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer" className="md-link">{children}</a>,
        hr: () => <hr className="md-hr" />,
      }}>
        {content}
      </ReactMarkdown>
    </div>
  )
}

const MemoMarkdown = memo(MarkdownContent)

function MsgBubble({ msg }: { msg: ChatMsg }) {
  const isUser = msg.role === 'user'
  if (msg.role === 'system') {
    return <div className="msg-system">{msg.content}</div>
  }
  return (
    <div className={`msg ${isUser ? 'user' : 'ai'}`}>
      {isUser ? <div className="msg-body msg-user-text">{msg.content}</div> : <MemoMarkdown content={msg.content} />}
    </div>
  )
}

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

  const current = skills.find(s => s.name === skill)
  const tag = current?.source?.startsWith('hermes') ? '📦' : current?.source === 'uploaded' ? '📤' : ''

  return (
    <div ref={ref} style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
      <div
        className={`skill-chip ${useSkill ? 'active' : ''}`}
        onClick={(e) => { e.stopPropagation(); onToggle() }}
      >
        <div className="skill-chip-dot" />
        <span
          className={`skill-chip-name ${!skill ? 'unset' : ''}`}
          onClick={(e) => { e.stopPropagation(); setOpen(!open); setTimeout(() => inputRef.current?.focus(), 50) }}
        >
          {tag} {skill || '选择 Skill'}
        </span>
        <span
          className="skill-chip-caret"
          onClick={(e) => { e.stopPropagation(); setOpen(!open); setTimeout(() => inputRef.current?.focus(), 50) }}
        >▼</span>
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
                <div>
                  <span className="sn">{s.name}</span>
                  {s.source?.startsWith('hermes') ? <span className="stag hermes">本地</span> : s.source === 'uploaded' ? <span className="stag uploaded">上传</span> : null}
                </div>
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

interface Props { onManageSkills: () => void }

export default function DiagnosisPanel({ onManageSkills }: Props) {
  const { state } = useApp()
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [stream, setStream] = useState('')
  const [sid, setSid] = useState<string | null>(null)
  const [skill, setSkill] = useState(state.skills[0]?.name || '')
  const [useSkill, setUseSkill] = useState(true)
  const [status, setStatus] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const prevStockRef = useRef<string | null>(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, stream])
  useEffect(() => {
    if (!skill && state.skills.length > 0) setSkill(state.skills[0].name)
  }, [state.skills])

  useEffect(() => {
    const code = state.currentStock?.code || null
    if (prevStockRef.current && code && code !== prevStockRef.current) {
      setMessages(p => [...p, { role: 'system', content: `已切换至 ${state.currentStock!.name} (${code})` }])
      setSid(null)
    }
    prevStockRef.current = code
  }, [state.currentStock?.code])

  const send = async () => {
    if (!input.trim() || loading) return
    const text = input.trim(); setInput('')
    setMessages(p => [...p, { role: 'user', content: text }])
    setLoading(true); setStream(''); setStatus('agent_starting')
    let full = ''
    await chatStream({
      session_id: sid || undefined, skill, use_skill: useSkill, message: text,
      stock_codes: state.currentStock ? [{ code: state.currentStock.code, name: state.currentStock.name }] : [],
    }, {
      onSessionId: id => setSid(id),
      onStatus: s => setStatus(s),
      onContent: c => { full += c; setStream(full); setStatus('') },
      onLog: () => { if (!status) setStatus('fetching_data') },
      onDone: () => { setMessages(p => [...p, { role: 'assistant', content: full }]); setStream(''); setLoading(false); setStatus('') },
      onError: e => { setMessages(p => [...p, { role: 'assistant', content: `Error: ${e}` }]); setStream(''); setLoading(false); setStatus('') },
    })
  }

  const statusText: Record<string, string> = { agent_starting: 'Agent 启动中...', fetching_data: '获取数据中...' }

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <span className="title">🧠 AI 诊断分析</span>
        <span style={{ flex: 1 }} />
        <SkillChip
          skills={state.skills}
          skill={skill}
          useSkill={useSkill}
          onToggle={() => setUseSkill(v => !v)}
          onPick={setSkill}
        />
        <button className="icon-btn" onClick={onManageSkills} title="管理 Skill">⚙</button>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && !stream && !loading && (
          <div className="chat-empty">
            <span style={{ fontSize: '2rem' }}>🤖</span>
            AI 股票诊断助手
            <span className="hint">选择股票后开始分析 · 支持多轮追问</span>
          </div>
        )}
        {messages.map((m, i) => <MsgBubble key={i} msg={m} />)}
        {stream && <div className="msg ai"><MemoMarkdown content={stream} /></div>}
        <div ref={bottomRef} />
      </div>

      {(loading || status) && (
        <div className="chat-status">
          <span className="dot" /> {statusText[status] || status || '处理中...'}
        </div>
      )}

      <div className="chat-input">
        <textarea
          value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
          placeholder={loading ? '等待回复...' : '输入分析问题...'}
          disabled={loading}
          rows={1}
        />
        <button onClick={send} disabled={loading || !input.trim()}>发送</button>
      </div>
    </div>
  )
}
