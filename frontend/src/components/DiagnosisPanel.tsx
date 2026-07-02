import { useState, useRef, useEffect } from 'react'
import { useApp } from '../contexts/AppContext'
import { chatStream } from '../api/diagnosis'
import ChatMessage from './ChatMessage'
import type { ChatMessage as ChatMsg } from '../types'

function loadApiKey(): string {
  return localStorage.getItem('ds_api_key') || ''
}

function saveApiKey(key: string) {
  localStorage.setItem('ds_api_key', key)
}

export default function DiagnosisPanel() {
  const { state } = useApp()
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [skill, setSkill] = useState(state.skills[0]?.name || '默认分析')
  const [apiKey, setApiKey] = useState(loadApiKey)
  const [showKey, setShowKey] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, streamingContent])

  const handleKeyChange = (val: string) => {
    setApiKey(val)
    saveApiKey(val)
  }

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
      model: 'deepseek-v4-pro',
      message: userMsg,
      stock_codes: state.currentStock ? [{ code: state.currentStock.code, name: state.currentStock.name }] : [],
      api_key: apiKey,
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
        setMessages(prev => [...prev, { role: 'assistant', content: `错误: ${err}` }])
        setStreamingContent('')
        setLoading(false)
      },
    })
  }

  const newSession = () => {
    setSessionId(null)
    setMessages([])
    setStreamingContent('')
  }

  return (
    <div style={{ background: '#222', borderRadius: 8, display: 'flex', flexDirection: 'column', height: 'calc(100vh - 80px)' }}>
      <div style={{ padding: 12, borderBottom: '1px solid #333' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <select value={skill} onChange={e => setSkill(e.target.value)}
            style={{ background: '#333', color: '#ddd', border: '1px solid #444', borderRadius: 6, padding: '4px 8px' }}>
            {state.skills.length > 0
              ? state.skills.map(s => <option key={s.name} value={s.name}>{s.name}</option>)
              : <option value="默认分析">默认分析</option>
            }
          </select>
          <span style={{ color: '#666', fontSize: 12 }}>
            {state.currentStock?.name || '选择股票'}
          </span>
          {sessionId && (
            <>
              <span style={{ color: '#555', fontSize: 11, marginLeft: 'auto' }}>#{sessionId.slice(0, 8)}</span>
              <button onClick={newSession} style={{ background: '#444', color: '#aaa', border: 'none', borderRadius: 4, padding: '2px 6px', cursor: 'pointer', fontSize: 11 }}>新建</button>
            </>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ color: '#888', fontSize: 11, whiteSpace: 'nowrap' }}>API Key:</span>
          <input
            type={showKey ? 'text' : 'password'}
            value={apiKey}
            onChange={e => handleKeyChange(e.target.value)}
            placeholder="sk-..."
            style={{ flex: 1, background: '#333', color: '#ddd', border: '1px solid #444', borderRadius: 4, padding: '3px 6px', fontSize: 12 }}
          />
          <button onClick={() => setShowKey(!showKey)}
            style={{ background: '#444', color: '#aaa', border: 'none', borderRadius: 4, padding: '2px 6px', cursor: 'pointer', fontSize: 11 }}>
            {showKey ? '隐藏' : '显示'}
          </button>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
        {messages.length === 0 && !streamingContent && (
          <div style={{ color: '#666', textAlign: 'center', marginTop: 40 }}>
            输入 DeepSeek API Key 并选择 Skill 和股票后，开始对话
          </div>
        )}
        {messages.map((m, i) => <ChatMessage key={i} role={m.role} content={m.content} />)}
        {streamingContent && <ChatMessage role="assistant" content={streamingContent} streaming />}
        <div ref={bottomRef} />
      </div>

      <div style={{ padding: 12, borderTop: '1px solid #333' }}>
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
          placeholder="输入分析问题... (Enter发送，Shift+Enter换行)"
          rows={2}
          style={{ width: '100%', background: '#333', color: '#ddd', border: '1px solid #444', borderRadius: 8, padding: 8, resize: 'none', fontSize: 14 }}
          disabled={loading}
        />
        <button onClick={send} disabled={loading}
          style={{ marginTop: 4, padding: '6px 16px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}>
          {loading ? '分析中...' : '发送'}
        </button>
      </div>
    </div>
  )
}
