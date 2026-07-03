# UI 4.0 Cyberpunk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 剔除 shadcn/ui 依赖，用纯 CSS 重建赛博朋克暗黑终端界面，修复 K 线图，左6右4分栏。

**Architecture:** CSS Grid + Flexbox + CSS Variables。扔掉 shadcn/ui、lucide-react、tailwind-merge、clsx。保留 lightweight-charts。后端不变。

**Tech Stack:** React 18, TypeScript, lightweight-charts v5, 纯 CSS

## Global Constraints

- 配色: bg=#08081a, surface=#10102a, accent=#00e5ff, up=#00e5ff, down=#ff3366
- 布局: CSS Grid `40px 1fr minmax(320px, 40%)`
- K线容器: `height: 45vh`（固定像素高度，不用百分比/100%）
- 全宽: 100vw, #root 无 max-width
- 对话: 左对齐 Markdown 渲染
- 所有按钮: title tooltip
- 不加新 npm 依赖

---

### Task 1: 清理 shadcn + 恢复纯 CSS 基础

**Files:**
- Modify: `frontend/package.json` — 移除 shadcn 相关 deps
- Delete: `frontend/src/components/ui/` 整个目录
- Delete: `frontend/src/lib/utils.ts`
- Delete: `frontend/components.json`
- Modify: `frontend/vite.config.ts` — 移除 tailwindcss 插件

- [ ] **Step 1: 卸载 shadcn 依赖**

```bash
cd frontend
npm uninstall @base-ui/react class-variance-authority lucide-react tailwind-merge clsx
npm uninstall tailwindcss @tailwindcss/vite
```

- [ ] **Step 2: 删除 shadcn 文件**

```bash
rm -rf src/components/ui src/lib/components.json
```

- [ ] **Step 3: 简化 vite.config.ts**

去掉 tailwindcss 导入，只保留 react：

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:8002' } },
})
```

- [ ] **Step 4: 验证**

```bash
npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "chore: remove shadcn/ui deps, restore pure css"
```

---

### Task 2: Cyberpunk 主题 CSS

**Files:**
- Modify: `frontend/src/index.css`
- Delete: `frontend/src/App.css`（合并进 index.css）

- [ ] **Step 1: Rewrite index.css**

```css
:root {
  --bg: #08081a;
  --surface: #10102a;
  --border: #1a1a3a;
  --text: #c8c8e0;
  --muted: #6b6b8a;
  --accent: #00e5ff;
  --accent2: #b44dff;
  --up: #00e5ff;
  --down: #ff3366;
  --chart-bg: #0a0a20;
  --glow: 0 0 12px rgba(0,229,255,0.25);
}

* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; font-size: 13px; }
#root { width: 100vw; min-height: 100vh; }

/* ===== Top Bar ===== */
.topbar {
  display: flex; align-items: center; gap: 10px;
  padding: 6px 14px; background: var(--surface);
  border-bottom: 1px solid var(--border); flex-shrink: 0;
}
.topbar .logo { font-size: 16px; font-weight: 700; color: var(--accent); white-space: nowrap; }
.topbar .search-wrap { flex: 1; max-width: 480px; position: relative; }
.topbar .search-wrap input {
  width: 100%; padding: 6px 12px; font-size: 13px; border-radius: 6px;
  border: 1px solid var(--border); background: var(--bg); color: var(--text); outline: none;
}
.topbar .search-wrap input:focus { border-color: var(--accent); box-shadow: var(--glow); }
.topbar button {
  background: var(--surface); color: var(--muted); border: 1px solid var(--border);
  border-radius: 6px; padding: 5px 10px; cursor: pointer; font-size: 12px;
}
.topbar button:hover { color: var(--accent); border-color: var(--accent); }

.search-dropdown {
  position: absolute; top: 36px; left: 0; right: 0; background: var(--surface);
  border: 1px solid var(--accent); border-radius: 6px; z-index: 100;
  max-height: 300px; overflow-y: auto; box-shadow: var(--glow);
}
.search-dropdown .item {
  padding: 8px 12px; cursor: pointer; display: flex; justify-content: space-between;
  border-bottom: 1px solid var(--border);
}
.search-dropdown .item:hover { background: rgba(0,229,255,0.08); }
.search-dropdown .item .code { color: var(--muted); font-size: 11px; }

/* ===== Main Grid ===== */
.main {
  display: grid;
  grid-template-columns: 40px 1fr minmax(320px, 40%);
  flex: 1; overflow: hidden;
}

/* ===== Icon Bar ===== */
.iconbar {
  width: 40px; background: var(--surface); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; align-items: center; padding-top: 8px;
  overflow: visible; position: relative; z-index: 50;
}
.iconbar .icon {
  width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;
  border-radius: 6px; cursor: pointer; margin-bottom: 4px; color: var(--muted); font-size: 16px;
}
.iconbar .icon:hover { background: rgba(0,229,255,0.1); color: var(--accent); }

.iconbar .watchlist-popup {
  display: none; position: absolute; left: 40px; top: 0;
  width: 200px; background: var(--surface); border: 1px solid var(--accent);
  border-radius: 0 8px 8px 0; box-shadow: var(--glow); z-index: 100;
}
.iconbar:hover .watchlist-popup { display: block; }
.watchlist-popup .item {
  padding: 8px 12px; cursor: pointer; font-size: 12px; border-bottom: 1px solid var(--border);
  display: flex; justify-content: space-between;
}
.watchlist-popup .item:hover { background: rgba(0,229,255,0.08); }
.watchlist-popup .item.active { border-left: 2px solid var(--accent); color: var(--accent); }

/* ===== Content (60%) ===== */
.content { display: flex; flex-direction: column; overflow: hidden; }
.price-header {
  display: flex; align-items: baseline; gap: 12px;
  padding: 8px 16px; background: var(--surface); border-bottom: 1px solid var(--border);
}
.price-header .name { font-size: 14px; color: var(--muted); }
.price-header .code { font-size: 11px; color: var(--muted); }
.price-header .price { font-size: 26px; font-weight: 700; }
.price-header .change { font-size: 15px; font-weight: 600; }

.kline-container { width: 100%; height: 45vh; background: var(--chart-bg); overflow: hidden; flex-shrink: 0; }

.info-row {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(90px, 1fr));
  gap: 6px; padding: 6px 12px; background: var(--surface);
  border-top: 1px solid var(--border); border-bottom: 1px solid var(--border);
}
.info-card {
  background: var(--bg); border: 1px solid var(--border); border-radius: 6px;
  padding: 5px 8px; text-align: center;
}
.info-card:hover { border-color: var(--accent); box-shadow: var(--glow); }
.info-card .lbl { color: var(--muted); font-size: 9px; text-transform: uppercase; }
.info-card .val { font-size: 13px; font-weight: 600; margin-top: 2px; }

/* ===== Right Panel (40%) ===== */
.right-panel {
  display: flex; flex-direction: column; border-left: 1px solid var(--border);
  background: var(--surface); overflow: hidden;
}
.right-panel .header {
  padding: 8px 12px; display: flex; align-items: center; gap: 8px;
  border-bottom: 1px solid var(--border);
}
.right-panel .header select {
  background: var(--bg); color: var(--text); border: 1px solid var(--border);
  border-radius: 4px; padding: 4px 8px; font-size: 11px;
}
.right-panel .messages {
  flex: 1; overflow-y: auto; padding: 10px;
  display: flex; flex-direction: column; gap: 6px;
}
.right-panel .messages .empty {
  text-align: center; color: var(--muted); margin-top: 60px; font-size: 14px;
}
.right-panel .input-area {
  padding: 8px 12px; display: flex; gap: 6px; align-items: flex-end;
  border-top: 1px solid var(--border);
}
.right-panel .input-area textarea {
  flex: 1; background: var(--bg); color: var(--text); border: 1px solid var(--border);
  border-radius: 6px; padding: 8px 10px; resize: none; font-size: 13px;
  outline: none; min-height: 38px; max-height: 100px; font-family: inherit;
}
.right-panel .input-area textarea:focus { border-color: var(--accent); }
.right-panel .input-area button {
  padding: 8px 16px; background: var(--accent); color: var(--bg);
  border: none; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 700;
}
.right-panel .input-area button:hover { box-shadow: var(--glow); }
.right-panel .input-area button:disabled { opacity: 0.4; cursor: default; }

/* ===== Messages ===== */
.msg-row { display: flex; margin-bottom: 2px; }
.msg-row.user { justify-content: flex-end; }
.msg-bubble { max-width: 88%; padding: 8px 12px; border-radius: 10px; font-size: 13px; line-height: 1.5; }
.msg-bubble.user { background: var(--accent); color: var(--bg); }
.msg-bubble.assistant { background: var(--bg); color: var(--text); border: 1px solid var(--border); }

/* ===== Markdown ===== */
.msg-bubble.assistant h2,.msg-bubble.assistant h3,.msg-bubble.assistant h4 { color: var(--accent); margin: 8px 0 4px; }
.msg-bubble.assistant h2 { font-size: 1.1em; }
.msg-bubble.assistant h3 { font-size: 1em; }
.msg-bubble.assistant h4 { font-size: 0.9em; }
.msg-bubble.assistant strong { color: var(--accent2); }
.msg-bubble.assistant table { border-collapse: collapse; margin: 6px 0; font-size: 12px; width: 100%; }
.msg-bubble.assistant td,.msg-bubble.assistant th { padding: 3px 8px; border: 1px solid var(--border); }
.msg-bubble.assistant th { background: rgba(0,229,255,0.1); color: var(--accent); }
.msg-bubble.assistant code { background: rgba(180,77,255,0.15); padding: 1px 5px; border-radius: 3px; font-size: 11px; color: var(--accent2); }
.msg-bubble.assistant blockquote { border-left: 2px solid var(--accent); padding: 4px 10px; margin: 6px 0; background: rgba(0,229,255,0.05); color: var(--muted); border-radius: 0 4px 4px 0; }
.msg-bubble.assistant ul,.msg-bubble.assistant ol { padding-left: 18px; margin: 4px 0; }

/* ===== Modal ===== */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 200; display: flex; align-items: center; justify-content: center; }
.modal { background: var(--surface); border: 1px solid var(--accent); border-radius: 12px; padding: 20px; width: 480px; max-height: 80vh; overflow-y: auto; box-shadow: var(--glow); }
.modal h2 { color: var(--accent); margin-bottom: 14px; font-size: 17px; }
.modal .skill-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; margin-bottom: 8px; }
.modal .skill-row .name { font-weight: 600; }
.modal .skill-row .desc { font-size: 11px; color: var(--muted); }
.modal .btn { padding: 6px 14px; border-radius: 6px; border: 1px solid var(--border); cursor: pointer; font-size: 12px; background: var(--bg); color: var(--text); }
.modal .btn:hover { border-color: var(--accent); }
.modal .btn-danger { color: var(--down); }
.modal .btn-primary { background: var(--accent); color: var(--bg); border-color: var(--accent); }
.modal .file-btn { display: block; margin-top: 12px; text-align: center; padding: 10px; background: var(--bg); border: 1px dashed var(--border); border-radius: 8px; cursor: pointer; color: var(--muted); }
.modal .file-btn:hover { border-color: var(--accent); color: var(--accent); }
.modal .file-btn input { display: none; }

@media (max-width: 768px) {
  .main { grid-template-columns: 1fr; }
  .iconbar { display: none; }
  .right-panel { display: none; }
}
```

- [ ] **Step 2: 验证没有 App.css 引用**

确认 App.tsx 不再 import `./App.css`

- [ ] **Step 3: 验证**

```bash
npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: cyberpunk dark CSS theme — full layout"
```

---

### Task 3: 重写组件（App + SearchBar + IconBar + Chat）

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/SearchBar.tsx`
- Modify: `frontend/src/components/DiagnosisPanel.tsx`
- Modify: `frontend/src/components/InfoCards.tsx`
- Modify: `frontend/src/components/KlineChart.tsx`
- Modify: `frontend/src/components/SkillManager.tsx`

- [ ] **Step 1: Write App.tsx**

```typescript
import { useEffect, useCallback } from 'react'
import { AppProvider, useApp } from './contexts/AppContext'
import { listSkills } from './api/skills'
import { getWatchlist } from './api/watchlist'
import SearchBar from './components/SearchBar'
import KlineChart from './components/KlineChart'
import InfoCards from './components/InfoCards'
import DiagnosisPanel from './components/DiagnosisPanel'
import SkillManager from './components/SkillManager'

function IconBar() {
  const { state, dispatch } = useApp()
  return (
    <div className="iconbar">
      <div className="icon" title="自选股">📊</div>
      <div className="watchlist-popup">
        {state.watchlist.map(s => (
          <div key={s.code} className={`item ${state.currentStock?.code === s.code ? 'active' : ''}`}
            onClick={() => dispatch({ type: 'SET_STOCK', stock: { code: s.code, name: s.name, market: s.market, industry: '' } })}>
            <span>{s.name}</span><span style={{color:'var(--muted)',fontSize:10}}>{s.code}</span>
          </div>
        ))}
        {state.watchlist.length === 0 && <div style={{padding:'8px 12px',fontSize:11,color:'var(--muted)'}}>搜索股票添加</div>}
      </div>
    </div>
  )
}

function AppShell() {
  const { state, dispatch } = useApp()
  const refreshSkills = useCallback(() => {
    listSkills().then(d => dispatch({ type: 'SET_SKILLS', skills: d.skills }))
  }, [dispatch])

  useEffect(() => {
    refreshSkills()
    getWatchlist().then(d => dispatch({ type: 'SET_WATCHLIST', watchlist: d.stocks }))
  }, [refreshSkills])

  return (
    <div style={{display:'flex',flexDirection:'column',height:'100vh',overflow:'hidden'}}>
      <div className="topbar">
        <span className="logo">◆ Stock Agent</span>
        <SearchBar />
        <button onClick={() => dispatch({ type: 'TOGGLE_SKILL_MANAGER' })} title="Skill管理">⚙ Skill</button>
      </div>
      <div className="main">
        <IconBar />
        <div className="content">
          {state.currentStock ? <><InfoCards /><KlineChart /></> : <div style={{flex:1,display:'flex',alignItems:'center',justifyContent:'center',color:'var(--muted)',fontSize:16}}>搜索股票开始分析</div>}
        </div>
        <DiagnosisPanel />
      </div>
      <SkillManager open={state.skillManagerOpen} onClose={() => dispatch({type:'TOGGLE_SKILL_MANAGER',open:false})} onRefresh={refreshSkills} />
    </div>
  )
}

export default function App() { return <AppProvider><AppShell /></AppProvider> }
```

- [ ] **Step 2: Write SearchBar.tsx**（保持功能不变，CSS class 适配）

```typescript
import { useState, useRef, useEffect } from 'react'
import { searchStocks } from '../api/stocks'
import { useApp } from '../contexts/AppContext'
import { addToWatchlist } from '../api/watchlist'
import type { StockInfo } from '../types'

export default function SearchBar() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<StockInfo[]>([])
  const [open, setOpen] = useState(false)
  const { state, dispatch } = useApp()
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h); return () => document.removeEventListener('mousedown', h)
  }, [])

  const handle = async (v: string) => {
    setQuery(v)
    if (v.length >= 1) { try { setResults((await searchStocks(v)).results); setOpen(true) } catch { setOpen(false) } }
    else setOpen(false)
  }

  const select = async (s: StockInfo) => {
    dispatch({ type: 'SET_STOCK', stock: s }); setQuery(s.name); setOpen(false)
    if (!state.watchlist.find(w => w.code === s.code)) {
      await addToWatchlist(s.code, s.name)
      dispatch({ type: 'SET_WATCHLIST', watchlist: (await (await import('../api/watchlist')).getWatchlist()).stocks })
    }
  }

  return (
    <div ref={ref} className="search-wrap">
      <input value={query} onChange={e => handle(e.target.value)} placeholder="搜索股票代码或名称..." />
      {open && results.length > 0 && (
        <div className="search-dropdown">
          {results.map(s => <div key={s.code} className="item" onClick={() => select(s)}><span>{s.name}</span><span className="code">{s.code}</span></div>)}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Write KlineChart.tsx**（用 CSS class `kline-container`）

保持逻辑不变，只改 return 部分：

```typescript
return (
  <div className="kline-container">
    <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
  </div>
)
```

- [ ] **Step 4: Write InfoCards.tsx**（用 CSS class `info-row` / `info-card`）

保持数据获取逻辑，改 JSX：

```typescript
// ... data fetching same ...
return (
  <div>
    <div className="price-header">
      <span className="name">{stock.name}</span>
      <span className="code">{stock.code}</span>
      <span className="price" style={{color: up ? 'var(--up)' : 'var(--down)'}}>{realtime?.price?.toFixed(2)||'--'}</span>
      <span className="change" style={{color: up ? 'var(--up)' : 'var(--down)'}}>{pct>0?'+':''}{pct.toFixed(2)}%</span>
    </div>
    <div className="info-row">
      {cards.map(c => <div key={c.label} className="info-card"><div className="lbl">{c.label}</div><div className="val" style={{color:c.color||undefined}}>{c.value}</div></div>)}
    </div>
  </div>
)
```

- [ ] **Step 5: Write DiagnosisPanel.tsx**（右面板）

```typescript
import { useState, useRef, useEffect, useMemo } from 'react'
import { useApp } from '../contexts/AppContext'
import { chatStream } from '../api/diagnosis'
import type { ChatMessage as ChatMsg } from '../types'

function renderMd(text: string): string {
  return text
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/^### (.+)$/gm,'<h4>$1</h4>').replace(/^## (.+)$/gm,'<h3>$1</h3>').replace(/^# (.+)$/gm,'<h2>$1</h2>')
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/`([^`]+)`/g,'<code>$1</code>')
    .replace(/^\|[-:\s|]+\|$/gm,'')
    .replace(/^\|(.+)\|$/gm,(_,c)=>'<tr>'+c.split('|').map((x:string)=>`<td>${x.trim()}</td>`).join('')+'</tr>')
    .replace(/((?:<tr>.*<\/tr>\n?)+)/g,'<table>$1</table>')
    .replace(/^- (.+)$/gm,'<li>$1</li>').replace(/((?:<li>.*<\/li>\n?)+)/g,'<ul>$1</ul>')
    .replace(/^&gt; (.+)$/gm,'<blockquote>$1</blockquote>')
    .replace(/\n/g,'<br/>')
}

function MsgBubble({ msg }: { msg: ChatMsg }) {
  const isUser = msg.role === 'user'
  const html = useMemo(() => isUser ? msg.content : renderMd(msg.content), [msg.content, isUser])
  return <div className={`msg-row ${isUser?'user':'assistant'}`}><div className={`msg-bubble ${isUser?'user':'assistant'}`} dangerouslySetInnerHTML={isUser?undefined:{__html:html}}>{isUser?msg.content:null}</div></div>
}

export default function DiagnosisPanel() {
  const { state } = useApp()
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [stream, setStream] = useState('')
  const [sid, setSid] = useState<string|null>(null)
  const [skill, setSkill] = useState(state.skills[0]?.name||'默认分析')
  const br = useRef<HTMLDivElement>(null)
  useEffect(()=>{br.current?.scrollIntoView({behavior:'smooth'})},[messages,stream])

  const send = async () => {
    if(!input.trim()||loading) return
    const um = input.trim(); setInput('')
    setMessages(p=>[...p,{role:'user',content:um}]); setLoading(true); setStream('')
    let fc = ''
    await chatStream({session_id:sid||undefined,skill,message:um,stock_codes:state.currentStock?[{code:state.currentStock.code,name:state.currentStock.name}]:[]},{
      onSessionId:id=>setSid(id), onContent:c=>{fc+=c;setStream(fc)},
      onDone:()=>{setMessages(p=>[...p,{role:'assistant',content:fc}]);setStream('');setLoading(false)},
      onError:e=>{setMessages(p=>[...p,{role:'assistant',content:`Error: ${e}`}]);setStream('');setLoading(false)},
    })
  }

  return (
    <div className="right-panel">
      <div className="header">
        <select value={skill} onChange={e=>setSkill(e.target.value)} title="分析Skill">
          {state.skills.length>0?state.skills.map(s=><option key={s.name} value={s.name}>{s.name}</option>):<option value="默认分析">默认分析</option>}
        </select>
        <span style={{fontSize:11,color:'var(--muted)',marginLeft:'auto'}}>{state.currentStock?.name||'选择股票'}</span>
      </div>
      <div className="messages">
        {messages.length===0&&!stream&&<div className="empty">输入分析问题开始对话</div>}
        {messages.map((m,i)=><MsgBubble key={i} msg={m}/>)}
        {stream&&<MsgBubble msg={{role:'assistant',content:stream}}/>}
        <div ref={br}/>
      </div>
      <div className="input-area">
        <textarea value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}}} placeholder="Enter 发送..." rows={1} disabled={loading}/>
        <button onClick={send} disabled={loading}>{loading?'...':'发送'}</button>
      </div>
    </div>
  )
}
```

- [ ] **Step 6: Write SkillManager.tsx**（纯 HTML modal）

```typescript
import { useState, useEffect } from 'react'
import { listSkills, uploadSkill, deleteSkill } from '../api/skills'
import type { SkillMeta } from '../types'

interface Props { open: boolean; onClose: () => void; onRefresh: () => void }

export default function SkillManager({ open, onClose, onRefresh }: Props) {
  const [skills, setSkills] = useState<SkillMeta[]>([])
  useEffect(() => { if (open) listSkills().then(d => setSkills(d.skills)) }, [open])
  if (!open) return null

  const up = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]; if (!f) return
    await uploadSkill(f); setSkills((await listSkills()).skills); onRefresh()
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div style={{display:'flex',justifyContent:'space-between',marginBottom:12}}>
          <h2 style={{margin:0}}>Skill 管理</h2>
          <button className="btn" onClick={onClose} style={{fontSize:18,lineHeight:1}}>✕</button>
        </div>
        {skills.map(s => (
          <div key={s.name} className="skill-row">
            <div><div className="name">{s.name}</div><div className="desc">{s.description||s.filename}</div></div>
            <button className="btn btn-danger" onClick={async()=>{await deleteSkill(s.name);setSkills((await listSkills()).skills);onRefresh()}}>删除</button>
          </div>
        ))}
        {skills.length===0&&<div style={{textAlign:'center',color:'var(--muted)',padding:20}}>暂无 Skill</div>}
        <label className="file-btn">导入 Skill (.md)<input type="file" accept=".md" onChange={up}/></label>
      </div>
    </div>
  )
}
```

- [ ] **Step 7: 移除 App.tsx 中 `import './App.css'`**

- [ ] **Step 8: 验证构建**

```bash
npx tsc --noEmit
```

- [ ] **Step 9: Commit**

```bash
git add -A && git commit -m "feat: cyberpunk components — app shell, searchbar, chat, skillmanager"
```

---

### Task 4: 集成验证 + 启动测试

- [ ] **Step 1: 后端健康检查**

```bash
cd backend && .venv/Scripts/python.exe -c "
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
assert c.get('/api/v1/health').status_code == 200
assert c.get('/api/v1/search?q=600519').status_code == 200
assert c.get('/api/v1/skills').status_code == 200
print('ALL OK')
"
```

- [ ] **Step 2: 前端构建验证**

```bash
cd frontend && npx tsc --noEmit && npx vite build --logLevel error
```

- [ ] **Step 3: 文件完整性检查**

```bash
ls frontend/src/components/App.tsx KlineChart.tsx InfoCards.tsx DiagnosisPanel.tsx SearchBar.tsx SkillManager.tsx
ls frontend/src/index.css
# 确认 shadcn 文件已删除
test ! -d frontend/src/components/ui && echo "shadcn removed OK"
```

- [ ] **Step 4: Commit + Push**

```bash
git add -A && git commit -m "chore: integration verification" && git push
```
