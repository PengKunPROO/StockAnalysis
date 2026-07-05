import { useState, useRef, useEffect } from 'react'
import { useApp } from '../contexts/AppContext'
import { chatStream } from '../api/diagnosis'
import type { ChatMessage as ChatMsg } from '../types'

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
  return (
    <div className={`msg ${isUser ? 'user' : 'ai'}`}>
      <div className="role">{isUser ? '你' : 'AI 分析'}</div>
      {isUser ? msg.content : <div className="msg-body" dangerouslySetInnerHTML={{ __html: renderMd(msg.content) }} />}
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

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, stream])
  useEffect(() => {
    if (!skill && state.skills.length > 0) setSkill(state.skills[0].name)
  }, [state.skills])

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
        {skill && <span className="subtitle">· {skill}</span>}
        <select value={skill} onChange={e => setSkill(e.target.value)}>
          <option value="">默认分析</option>
          {state.skills.map(s => (
            <option key={s.name} value={s.name}>{s.name}{s.source?.startsWith('hermes') ? ' 📦' : s.source === 'uploaded' ? ' 📤' : ''}</option>
          ))}
        </select>
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
