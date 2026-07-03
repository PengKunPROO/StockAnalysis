import { useState, useRef, useEffect, useMemo } from 'react'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Textarea } from '@/components/ui/textarea'
import { useApp } from '../contexts/AppContext'
import { chatStream } from '../api/diagnosis'
import type { ChatMessage as ChatMsg } from '../types'

function renderMd(text: string): string {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^### (.+)$/gm, '<h4 style="margin:10px 0 4px;font-size:15px;color:#1a1a2e;font-weight:600">$1</h4>')
    .replace(/^## (.+)$/gm, '<h3 style="margin:12px 0 6px;font-size:17px;color:#1a1a2e;font-weight:700">$1</h3>')
    .replace(/^# (.+)$/gm, '<h2 style="margin:16px 0 8px;font-size:20px;color:#1a1a2e;font-weight:700">$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong style="color:#2962ff">$1</strong>')
    .replace(/`([^`]+)`/g, '<code style="background:#f0f0f0;padding:1px 5px;border-radius:3px;font-size:13px">$1</code>')
    .replace(/^\|[-:\s|]+\|$/gm, '')
    .replace(/^\|(.+)\|$/gm, (_, cells) => '<tr>' + cells.split('|').map((c: string) => `<td style="padding:4px 10px;border:1px solid #e0e0e0">${c.trim()}</td>`).join('') + '</tr>')
    .replace(/((?:<tr>.*<\/tr>\n?)+)/g, '<table style="border-collapse:collapse;margin:8px 0;font-size:13px;width:100%">$1</table>')
    .replace(/^- (.+)$/gm, '<li style="margin:2px 0">$1</li>')
    .replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul style="margin:4px 0;padding-left:20px">$1</ul>')
    .replace(/^&gt; (.+)$/gm, '<blockquote style="border-left:3px solid #2962ff;padding:6px 12px;margin:8px 0;background:#f5f7ff;border-radius:0 6px 6px 0;color:#555">$1</blockquote>')
    .replace(/\n/g, '<br/>')
}

function MsgBubble({ msg }: { msg: ChatMsg }) {
  const isUser = msg.role === 'user'
  const html = useMemo(() => isUser ? msg.content : renderMd(msg.content), [msg.content, isUser])
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-1`}>
      <div
        className={`max-w-[85%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${isUser ? 'bg-accent text-white' : 'bg-surface border border-border text-text'}`}
        dangerouslySetInnerHTML={isUser ? undefined : { __html: html }}
      >
        {isUser ? msg.content : null}
      </div>
    </div>
  )
}

export default function DiagnosisPanel() {
  const { state } = useApp()
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
      session_id: sessionId || undefined, skill, message: userMsg,
      stock_codes: state.currentStock ? [{ code: state.currentStock.code, name: state.currentStock.name }] : [],
    }, {
      onSessionId: (id) => setSessionId(id),
      onContent: (chunk) => { fullContent += chunk; setStreamingContent(fullContent) },
      onDone: () => { setMessages(prev => [...prev, { role: 'assistant', content: fullContent }]); setStreamingContent(''); setLoading(false) },
      onError: (err) => { setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${err}` }]); setStreamingContent(''); setLoading(false) },
    })
  }

  return (
    <>
      <ScrollArea className="flex-[1_1_0] min-h-0 px-5 py-3">
        {messages.length === 0 && !streamingContent && (
          <div className="text-center text-muted mt-20 text-base">
            {state.currentStock ? `已选中 ${state.currentStock.name}，在下方输入分析问题` : '搜索一只股票，然后在下方使用 AI 分析'}
          </div>
        )}
        {messages.map((m, i) => <MsgBubble key={i} msg={m} />)}
        {streamingContent && <MsgBubble msg={{ role: 'assistant', content: streamingContent }} />}
        <div ref={bottomRef} />
      </ScrollArea>

      <div className="flex items-end gap-2 px-4 py-3 bg-surface border-t border-border flex-shrink-0">
        <Select value={skill} onValueChange={setSkill}>
          <SelectTrigger className="w-[120px] h-9 text-xs" title="选择分析 Skill">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {state.skills.length > 0
              ? state.skills.map(s => <SelectItem key={s.name} value={s.name}>{s.name}</SelectItem>)
              : <SelectItem value="默认分析">默认分析</SelectItem>}
          </SelectContent>
        </Select>
        <Textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
          placeholder={state.currentStock ? `询问关于 ${state.currentStock.name}...` : '输入分析问题 (Enter发送)'}
          rows={1}
          disabled={loading}
          className="flex-1 min-h-[40px] max-h-[120px] resize-none"
        />
        <Button onClick={send} disabled={loading} size="sm" className="h-10 px-5">
          {loading ? '分析中...' : '发送'}
        </Button>
      </div>
    </>
  )
}
