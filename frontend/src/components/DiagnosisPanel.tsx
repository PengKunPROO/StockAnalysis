import { useState, useRef, useEffect } from 'react'
import { useApp } from '../contexts/AppContext'
import { chatStream } from '../api/diagnosis'
import type { ChatMessage as ChatMsg, SkillMeta } from '../types'

function renderMd(text: string): string {
  let html = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  html = html.replace(/(^\|.+\|$\n?)+/gm, (block: string) => {
    const rows = block.trim().split('\n').filter(r => r.includes('|'))
    if (rows.length < 2) return block
    const cells = (r: string) => r.split('|').filter((_, i, a) => i > 0 && i < a.length - 1).map(c => c.trim())
    const sep = rows[1]
    if (!sep || !/^[|\s\-:]+$/.test(sep.replace(/\|/g, '').trim())) return block
    return `<table><thead><tr>${cells(rows[0]).map(c => `<th>${c}</th>`).join('')}</tr></thead><tbody>${rows.slice(2).map(r => `<tr>${cells(r).map(c => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table>`
  })
  html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>').replace(/^## (.+)$/gm, '<h3>$1</h3>').replace(/^# (.+)$/gm, '<h2>$1</h2>')
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>').replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>')
  html = html.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
  html = html.replace(/\n/g, '<br/>')
  return html
}

function MsgBubble({ msg }: { msg: ChatMsg }) {
  const isUser = msg.role === 'user'
  if (msg.role === 'system') {
    return <div className="msg-system">{msg.content}</div>
  }
  return (
    <div className={`msg ${isUser ? 'user' : 'ai'}`}>
      <div className="role">{isUser ? '你' : 'AI 分析'}</div>
      {isUser ? msg.content : <div className="msg-body" dangerouslySetInnerHTML={{ __html: renderMd(msg.content) }} />}
    </div>
  )
}

function SkillPicker({ skills, value, onChange }: { skills: SkillMeta[]; value: string; onChange: (name: string) => void }) {
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

  const current = skills.find(s => s.name === value)
  const tag = current?.source?.startsWith('hermes') ? '📦' : current?.source === 'uploaded' ? '📤' : ''

  return (
    <div ref={ref} style={{ position: 'relative', marginLeft: 'auto' }}>
      <button className="skill-trigger" onClick={() => { setOpen(!open); setTimeout(() => inputRef.current?.focus(), 50) }}>
        {tag} {value || '选择 Skill'}
      </button>
      {open && (
        <div className="skill-dropdown">
          <input ref={inputRef} className="skill-search" value={query} onChange={e => setQuery(e.target.value)}
            placeholder="搜索 Skill 名称..." onKeyDown={e => { if (e.key === 'Escape') setOpen(false) }} />
          <div className="skill-list">
            {filtered.map(s => (
              <div key={s.name} className={`skill-opt ${s.name === value ? 'sel' : ''}`} onClick={() => { onChange(s.name); setOpen(false); setQuery('') }}>
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
  const [status, setStatus] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const prevStockRef = useRef<string | null>(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, stream])
  useEffect(() => {
    if (!skill && state.skills.length > 0) setSkill(state.skills[0].name)
  }, [state.skills])

  // Detect stock change -> insert context marker
  useEffect(() => {
    const code = state.currentStock?.code || null
    if (prevStockRef.current && code && code !== prevStockRef.current) {
      setMessages(p => [...p, { role: 'system', content: `已切换至 ${state.currentStock!.name} (${code})` }])
      setSid(null) // start fresh session on stock switch
    }
    prevStockRef.current = code
  }, [state.currentStock?.code])

  const send = async () => {
    if (!input.trim() || loading) return
    const text = input.trim(); setInput('')
    setMessages(p => [...p, { role: 'user', content: text }]); setLoading(true); setStream(''); setStatus('agent_starting')
    let full = ''
    await chatStream({
      session_id: sid || undefined, skill, message: text,
      stock_codes: state.currentStock ? [{ code: state.currentStock.code, name: state.currentStock.name }] : [],
    }, {
      onSessionId: id => setSid(id),
      onStatus: s => setStatus(s),
      onContent: c => { full += c; setStream(full); setStatus('') },
      onDone: () => { setMessages(p => [...p, { role: 'assistant', content: full }]); setStream(''); setLoading(false); setStatus('') },
      onError: e => { setMessages(p => [...p, { role: 'assistant', content: `Error: ${e}` }]); setStream(''); setLoading(false); setStatus('') },
    })
  }

  const statusText: Record<string, string> = { agent_starting: 'Agent 启动中...', fetching_data: '获取数据中...' }

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <span className="title">🧠 AI 诊断分析</span>
        <SkillPicker skills={state.skills} value={skill} onChange={setSkill} />
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
        {stream && <MsgBubble msg={{ role: 'assistant', content: stream }} />}
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
