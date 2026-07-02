import { useState, useRef, useEffect, useMemo } from 'react'
import { useApp } from '../contexts/AppContext'
import { chatStream } from '../api/diagnosis'
import type { ChatMessage as ChatMsg } from '../types'

function renderMd(text: string): string {
  let html = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^# (.+)$/gm, '<h2>$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^\|[-:\s|]+\|$/gm, '')
    .replace(/^\|(.+)\|$/gm, (_, cells) => {
      const tds = cells.split('|').map((c: string) =>
        `<td>${c.trim()}</td>`
      ).join('')
      return `<tr>${tds}</tr>`
    })
    .replace(/((?:<tr>.*<\/tr>\n?)+)/g, '<table>$1</table>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>')
    .replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>')
    .replace(/\n/g, '<br/>')
  return html
}

function MsgBubble({ msg }: { msg: ChatMsg }) {
  const isUser = msg.role === 'user'
  const html = useMemo(() => isUser ? msg.content : renderMd(msg.content), [msg.content, isUser])

  return (
    <div className={`msg-row ${isUser ? 'user' : 'assistant'}`}>
      <div
        className={`msg-bubble ${isUser ? 'user' : 'assistant'}`}
        dangerouslySetInnerHTML={isUser ? undefined : { __html: html }}
      >
        {isUser ? msg.content : null}
      </div>
    </div>
  )
}

export default function DiagnosisPanel() {
  const { state, dispatch } = useApp()
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [skill, setSkill] = useState(state.skills[0]?.name || '默认分析')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, streamingContent])

  const send = async () => {
    if (!input.trim() || loading) return
    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMsg }])
    setLoading(true)
    setStreamingContent('')

    let fullContent = ''
    await chatStream({
      session_id: sessionId || undefined,
      skill,
      message: userMsg,
      stock_codes: state.currentStock ? [{ code: state.currentStock.code, name: state.currentStock.name }] : [],
    }, {
      onSessionId: (id) => setSessionId(id),
      onContent: (chunk) => {
        fullContent += chunk
        setStreamingContent(fullContent)
      },
      onDone: () => {
        setMessages(prev => [...prev, { role: 'assistant', content: fullContent }])
        setStreamingContent('')
        setLoading(false)
      },
      onError: (err) => {
        setMessages(prev => [...prev, { role: 'assistant', content: `❌ ${err}` }])
        setStreamingContent('')
        setLoading(false)
      },
    })
  }

  return (
    <>
      <div className="chat-area">
        {messages.length === 0 && !streamingContent && (
          <div className="empty">
            {state.currentStock
              ? `已选中 ${state.currentStock.name}，在下方输入分析问题`
              : '搜索一只股票，然后在下方使用 AI 分析'}
          </div>
        )}
        {messages.map((m, i) => <MsgBubble key={i} msg={m} />)}
        {streamingContent && <MsgBubble msg={{ role: 'assistant', content: streamingContent }} />}
        <div ref={bottomRef} />
      </div>

      <div className="chat-input-area">
        <select
          className="skill-select"
          value={skill}
          onChange={e => setSkill(e.target.value)}
          title="选择分析 Skill"
        >
          {state.skills.length > 0
            ? state.skills.map(s => <option key={s.name} value={s.name}>{s.name}</option>)
            : <option value="默认分析">默认分析</option>
          }
        </select>
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
          }}
          placeholder={state.currentStock ? `询问关于 ${state.currentStock.name} 的问题...` : '输入分析问题...'}
          rows={1}
          disabled={loading}
        />
        <button onClick={send} disabled={loading}>
          {loading ? '分析中...' : '发送'}
        </button>
      </div>
    </>
  )
}
