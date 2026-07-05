import { useState, useRef, useEffect, useMemo } from 'react'
import { useApp } from '../contexts/AppContext'
import { chatStream } from '../api/diagnosis'
import type { ChatMessage as ChatMsg } from '../types'

function renderMd(text: string): string {
  let html = text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
  html = html.replace(/(^\|.+\|$\n?)+/gm, (block: string) => {
    const rows = block.trim().split('\n').filter(r => r.includes('|'))
    if (rows.length < 2) return block
    const cells = (r:string) => r.split('|').filter((_,i,a)=>i>0&&i<a.length-1).map(c => c.trim())
    const sep = rows[1]
    if (!sep || !/^[|s\-:]+$/.test(sep.replace(/\|/g,'').trim())) return block
    const thead = `<tr>${cells(rows[0]).map(c=>`<th>${c}</th>`).join('')}</tr>`
    const tbody = rows.slice(2).map(r => `<tr>${cells(r).map(c=>`<td>${c}</td>`).join('')}</tr>`).join('')
    return `<table>${thead}${tbody}</table>`
  })
  html = html.replace(/^### (.+)$/gm,'<h4>$1</h4>').replace(/^## (.+)$/gm,'<h3>$1</h3>').replace(/^# (.+)$/gm,'<h2>$1</h2>')
  html = html.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
  html = html.replace(/`([^`]+)`/g,'<code>$1</code>')
  html = html.replace(/^- (.+)$/gm,'<li>$1</li>')
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g,'<ul>$1</ul>')
  html = html.replace(/^> (.+)$/gm,'<blockquote>$1</blockquote>')
  html = html.replace(/\n/g,'<br/>')
  return html
}

function MsgBubble({ msg }: { msg: ChatMsg }) {
  const isUser = msg.role === 'user'
  return <div className={`msg-row ${isUser?'user':'ai'}`}>
    <div className="role">{isUser?'你':'AI 助手'}</div>
    <div className="msg-bubble" dangerouslySetInnerHTML={isUser?undefined:{__html:renderMd(msg.content)}}>{isUser?msg.content:null}</div>
  </div>
}

interface Props { onManageSkills: () => void }

export default function DiagnosisPanel({ onManageSkills }: Props) {
  const { state } = useApp()
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [stream, setStream] = useState('')
  const [sid, setSid] = useState<string|null>(null)
  const [skill, setSkill] = useState(state.skills[0]?.name||'默认分析')
  const [status, setStatus] = useState('')
  const br = useRef<HTMLDivElement>(null)
  useEffect(()=>{br.current?.scrollIntoView({behavior:'smooth'})},[messages,stream])

  const send = async () => {
    if (!input.trim() || loading) return
    const um = input.trim(); setInput('')
    setMessages(p=>[...p,{role:'user',content:um}]); setLoading(true); setStream(''); setStatus('agent_starting')
    let fc = ''
    await chatStream({session_id:sid||undefined,skill,message:um,stock_codes:state.currentStock?[{code:state.currentStock.code,name:state.currentStock.name}]:[]},{
      onSessionId:id=>setSid(id), onStatus:s=>setStatus(s),
      onContent:c=>{fc+=c;setStream(fc);setStatus('')},
      onDone:()=>{setMessages(p=>[...p,{role:'assistant',content:fc}]);setStream('');setLoading(false);setStatus('')},
      onError:e=>{setMessages(p=>[...p,{role:'assistant',content:`Error: ${e}`}]);setStream('');setLoading(false);setStatus('')},
    })
  }

  return (
    <div className="right">
      <div className="rhd">
        🤖 AI 分析
        <select value={skill} onChange={e=>setSkill(e.target.value)} title="分析Skill">
          {state.skills.map(s=><option key={s.name} value={s.name}>{s.name}</option>)}
          {state.skills.length===0 && <option value="默认分析">默认分析</option>}
        </select>
        <span className="icon" onClick={onManageSkills} title="管理Skill">⚙</span>
      </div>
      <div className="messages">
        {messages.length===0&&!stream&&!loading&&<div className="empty">输入分析问题开始对话</div>}
        {messages.map((m,i)=><MsgBubble key={i} msg={m}/>)}
        {loading&&status&&<div className="msg-row ai"><div className="role">AI 助手</div><div className="msg-bubble" style={{opacity:.6,fontStyle:'italic'}}>🤖 Agent 运行中...</div></div>}
        {stream&&<MsgBubble msg={{role:'assistant',content:stream}}/>}
        <div ref={br}/>
      </div>
      <div className="input-area">
        <textarea value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}}} placeholder="提问..."/>
        <button onClick={send} disabled={loading}>{loading?'...':'发送'}</button>
      </div>
    </div>
  )
}
