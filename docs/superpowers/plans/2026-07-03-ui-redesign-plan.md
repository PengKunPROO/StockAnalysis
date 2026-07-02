# UI 3.0 Implementation Plan — shadcn/ui + Agent Mode

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 将前端从裸 CSS 迁移到 shadcn/ui + Tailwind，实现 TradingView 浅色专业风，并将 AI 诊断改为 Agent 模式（Hermes 自行 curl 数据 API）。

**Architecture:** React + TypeScript + shadcn/ui + Tailwind CSS。后端诊断端点 prompt 结构改为 API 端点说明，Hermes 通过 terminal 工具 curl 获取数据。

**Tech Stack:** React 18, Tailwind CSS v4, shadcn/ui, lightweight-charts v5, TypeScript

## Global Constraints

- Vite dev port: 8002 proxy → backend localhost:8002
- Stock code format: sh.600519 / sz.000001
- 配色 TradingView 浅色风: bg=#f5f5f5, card=#fff, accent=#2962ff
- 所有按钮必须有 title/tooltip
- 聊天消息左对齐
- 2K 屏幕 100vw 无空白

---

### Task 1: Tailwind + shadcn/ui 脚手架

**Files:**
- Create: `frontend/tailwind.config.ts`, `frontend/postcss.config.js`
- Modify: `frontend/src/index.css`, `frontend/src/App.css`
- Create: `frontend/src/lib/utils.ts`
- Create: `frontend/components.json` (shadcn config)

- [ ] **Step 1: Install Tailwind CSS v4 + shadcn/ui CLI**

```bash
cd frontend
npm install -D tailwindcss @tailwindcss/vite
npm install -D @types/node
npx shadcn@latest init -d
```

- [ ] **Step 2: Configure Vite for Tailwind**

Update `vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { '/api': 'http://localhost:8002' } },
})
```

- [ ] **Step 3: Rewrite index.css with TradingView theme**

```css
@import "tailwindcss";

@theme {
  --color-bg: #f5f5f5;
  --color-surface: #ffffff;
  --color-border: #e0e0e0;
  --color-text: #1a1a2e;
  --color-muted: #6b7280;
  --color-accent: #2962ff;
  --color-up: #089981;
  --color-down: #f23645;
  --color-sidebar: #fafafa;
}

body { margin: 0; background: var(--color-bg); color: var(--color-text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
#root { width: 100vw; min-height: 100vh; }
```

- [ ] **Step 4: Create shadcn utils**

`frontend/src/lib/utils.ts`:
```typescript
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```
Install: `npm install clsx tailwind-merge`

- [ ] **Step 5: Install shadcn components**

```bash
npx shadcn@latest add card input select button scroll-area sheet separator
```

- [ ] **Step 6: Verify build**

```bash
npx tsc --noEmit && npx vite build --logLevel error
```

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: tailwind + shadcn/ui scaffolding, tradingview theme"
```

---

### Task 2: Rewrite App Shell (TopBar + Sidebar)

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.css` → delete, replaced by Tailwind

- [ ] **Step 1: Delete App.css imports, rewrite App.tsx**

```typescript
import { useEffect, useCallback, useState } from 'react'
import { AppProvider, useApp } from './contexts/AppContext'
import { listSkills } from './api/skills'
import { getWatchlist } from './api/watchlist'
import SearchBar from './components/SearchBar'
import KlineChart from './components/KlineChart'
import InfoCards from './components/InfoCards'
import DiagnosisPanel from './components/DiagnosisPanel'
import SkillManager from './components/SkillManager'
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Menu, Settings } from 'lucide-react'

function Sidebar() {
  const { state, dispatch } = useApp()
  return (
    <div className="flex flex-col h-full bg-sidebar">
      <div className="px-4 py-3 text-xs text-muted uppercase tracking-wider font-semibold">自选股</div>
      {state.watchlist.map(s => (
        <div
          key={s.code}
          onClick={() => dispatch({ type: 'SET_STOCK', stock: { code: s.code, name: s.name, market: s.market, industry: '' } })}
          className={`px-4 py-2 cursor-pointer text-sm border-b border-border hover:bg-gray-100 transition-colors ${state.currentStock?.code === s.code ? 'bg-blue-50 border-l-[3px] border-l-accent font-semibold' : ''}`}
        >
          {s.name}
          <span className="text-xs text-muted ml-2">{s.code}</span>
        </div>
      ))}
      {state.watchlist.length === 0 && (
        <div className="px-4 py-3 text-sm text-muted">搜索股票添加</div>
      )}
    </div>
  )
}

function AppShell() {
  const { state, dispatch } = useApp()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const refreshSkills = useCallback(() => {
    listSkills().then(d => dispatch({ type: 'SET_SKILLS', skills: d.skills }))
  }, [dispatch])

  useEffect(() => {
    refreshSkills()
    getWatchlist().then(d => dispatch({ type: 'SET_WATCHLIST', watchlist: d.stocks }))
  }, [refreshSkills])

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      {/* TopBar */}
      <div className="flex items-center gap-3 px-4 py-2 bg-surface border-b border-border flex-shrink-0">
        <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" title="自选股列表"><Menu className="h-5 w-5" /></Button>
          </SheetTrigger>
          <SheetContent side="left" className="p-0 w-[240px]">
            <Sidebar />
          </SheetContent>
        </Sheet>
        <span className="font-bold text-lg text-accent whitespace-nowrap">Stock Agent</span>
        <SearchBar />
        <Button variant="outline" size="sm" onClick={() => dispatch({ type: 'TOGGLE_SKILL_MANAGER' })} title="管理分析 Skill">
          <Settings className="h-4 w-4 mr-1" /> Skill
        </Button>
      </div>

      {/* Main content */}
      <div className="flex-1 overflow-hidden">
        {state.currentStock ? (
          <div className="flex flex-col h-full">
            <div className="flex-shrink-0">
              <InfoCards />
              <KlineChart />
              <Separator />
            </div>
            <DiagnosisPanel />
          </div>
        ) : (
          <div className="flex-1 flex flex-col"><DiagnosisPanel /></div>
        )}
      </div>

      <SkillManager
        open={state.skillManagerOpen}
        onClose={() => dispatch({ type: 'TOGGLE_SKILL_MANAGER', open: false })}
        onRefresh={refreshSkills}
      />
    </div>
  )
}

export default function App() {
  return <AppProvider><AppShell /></AppProvider>
}
```

- [ ] **Step 2: Install lucide-react icons**

```bash
npm install lucide-react
```

- [ ] **Step 3: Verify build**

```bash
npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: app shell with shadcn/ui — topbar, sidebar sheet"
```

---

### Task 3: Rewrite SearchBar + InfoCards

**Files:**
- Modify: `frontend/src/components/SearchBar.tsx`
- Modify: `frontend/src/components/InfoCards.tsx`

- [ ] **Step 1: Rewrite SearchBar with shadcn Input**

```typescript
import { useState, useRef, useEffect } from 'react'
import { Input } from '@/components/ui/input'
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
    const handler = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleInput = async (val: string) => {
    setQuery(val)
    if (val.length >= 1) {
      try { const data = await searchStocks(val); setResults(data.results); setOpen(true) } catch { setOpen(false) }
    } else { setOpen(false) }
  }

  const select = async (s: StockInfo) => {
    dispatch({ type: 'SET_STOCK', stock: s })
    setQuery(s.name)
    setOpen(false)
    if (!state.watchlist.find(w => w.code === s.code)) {
      try {
        await addToWatchlist(s.code, s.name)
        const { getWatchlist } = await import('../api/watchlist')
        dispatch({ type: 'SET_WATCHLIST', watchlist: (await getWatchlist()).stocks })
      } catch {}
    }
  }

  return (
    <div ref={ref} className="flex-1 max-w-[480px] relative">
      <Input
        value={query}
        onChange={e => handleInput(e.target.value)}
        placeholder="搜索股票代码或名称..."
        className="w-full"
      />
      {open && results.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-surface border border-border rounded-lg shadow-lg z-50 max-h-[300px] overflow-y-auto">
          {results.map(s => (
            <div key={s.code} onClick={() => select(s)} className="px-4 py-2.5 cursor-pointer hover:bg-gray-50 border-b border-border flex justify-between items-center transition-colors">
              <span className="font-medium text-sm">{s.name}</span>
              <span className="text-xs text-muted">{s.code}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Rewrite InfoCards with shadcn Card**

```typescript
import { useState, useEffect } from 'react'
import { Card } from '@/components/ui/card'
import { useApp } from '../contexts/AppContext'
import { getRealtime, getFinancial, getIndicators } from '../api/stocks'
import type { IndicatorPoint } from '../types'

export default function InfoCards() {
  const { state } = useApp()
  const stock = state.currentStock
  const [realtime, setRealtime] = useState<any>(null)
  const [financial, setFinancial] = useState<any>(null)
  const [indicators, setIndicators] = useState<IndicatorPoint | null>(null)

  useEffect(() => {
    if (!stock) return
    getRealtime(stock.code).then(setRealtime).catch(() => {})
    getFinancial(stock.code).then(d => setFinancial(d.reports?.[0])).catch(() => {})
    getIndicators(stock.code, 60).then(d => setIndicators(d.data?.[d.data.length - 1] || null))
  }, [stock])

  if (!stock) return null

  const pct = realtime?.change_pct ?? 0
  const up = pct >= 0
  const cards = [
    { label: '最新价', value: realtime?.price?.toFixed(2) || '--', color: up ? 'text-up' : 'text-down' },
    { label: '涨跌幅', value: `${pct > 0 ? '+' : ''}${pct.toFixed(2)}%`, color: up ? 'text-up' : 'text-down' },
    { label: '成交量', value: realtime?.volume ? `${(realtime.volume / 10000).toFixed(0)}万` : '--' },
    { label: 'ROE', value: financial?.roe != null ? `${financial.roe.toFixed(1)}%` : '--' },
    { label: '负债率', value: financial?.debt_ratio != null ? `${financial.debt_ratio.toFixed(1)}%` : '--' },
    { label: 'MACD', value: indicators?.macd ? `${indicators.macd.macd > 0 ? '金叉' : '死叉'} ${indicators.macd.macd.toFixed(1)}` : '--', color: (indicators?.macd?.macd ?? 0) > 0 ? 'text-up' : 'text-down' },
    { label: 'RSI(14)', value: indicators?.rsi?.rsi14?.toFixed(0) || '--', color: (indicators?.rsi?.rsi14 ?? 50) > 70 ? 'text-down' : (indicators?.rsi?.rsi14 ?? 50) < 30 ? 'text-up' : '' },
    { label: 'KDJ', value: indicators?.kdj?.k != null ? `K${indicators.kdj.k.toFixed(0)} D${indicators.kdj.d.toFixed(0)}` : '--' },
  ]

  return (
    <div>
      <div className="flex items-baseline gap-4 px-5 py-3 bg-surface">
        <span className="text-muted text-sm">{stock.name}</span>
        <span className="text-xs text-muted">{stock.code}</span>
        <span className="text-2xl font-bold">{realtime?.price?.toFixed(2) || '--'}</span>
        <span className={`text-base font-semibold ${up ? 'text-up' : 'text-down'}`}>
          {pct > 0 ? '+' : ''}{pct.toFixed(2)}%
        </span>
      </div>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(100px,1fr))] gap-2 px-4 pb-3">
        {cards.map(c => (
          <Card key={c.label} className="p-2.5 text-center shadow-none border border-border/50">
            <div className="text-[10px] text-muted whitespace-nowrap">{c.label}</div>
            <div className={`text-sm font-semibold ${c.color || ''}`}>{c.value}</div>
          </Card>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Verify build**

```bash
npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: SearchBar + InfoCards with shadcn/ui"
```

---

### Task 4: Chat UI (DiagnosisPanel)

**Files:**
- Modify: `frontend/src/components/DiagnosisPanel.tsx`
- Delete: `frontend/src/components/ChatMessage.tsx` (merged into DiagnosisPanel)

- [ ] **Step 1: Rewrite DiagnosisPanel**

```typescript
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
      <ScrollArea className="flex-1 px-5 py-3">
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
```

Install: `npm install @radix-ui/react-select @radix-ui/react-scroll-area`

- [ ] **Step 2: Verify build**

```bash
npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat: chat UI with shadcn/ui — select, textarea, bubble"
```

---

### Task 5: Agent Mode — Backend Prompt Update

**Files:**
- Modify: `backend/app/api/v1/diagnosis.py`

- [ ] **Step 1: Replace pre-fetch data injection with curl API instructions**

Change the prompt construction in `diagnosis.py`:

```python
    # Build agent prompt with API instructions (no pre-fetch)
    stock_list = ", ".join(f"{s['name']}({s['code']})" for s in stocks)
    prompt = f"""{skill_content}

你是股票分析 Agent。可以通过终端运行 curl 获取数据。当前后端运行在 localhost:8002。

## 可用数据 API:

搜索股票:
  curl -s "http://localhost:8002/api/v1/search?q=<关键词>"

实时行情:
  curl -s "http://localhost:8002/api/v1/stock/<代码>/realtime"

历史K线 (日线):
  curl -s "http://localhost:8002/api/v1/stock/<代码>/kline?period=daily&start=YYYY-MM-DD&end=YYYY-MM-DD"

技术指标 (MACD/RSI/KDJ/BOLL):
  curl -s "http://localhost:8002/api/v1/stock/<代码>/indicators?days=60"

财务数据 (ROE/负债率/毛利率等):
  curl -s "http://localhost:8002/api/v1/stock/<代码>/financial"

## 当前分析标的:
{stock_list}

## 规则:
1. 需要数据时主动 curl 获取，不要编造
2. 股票代码格式: sh.600519, sz.000001
3. 数据返回 JSON 格式，提取 relevant 字段分析
4. 用 Markdown 表格呈现关键指标
5. 给出客观分析，不做买卖建议

用户问题: {req.message}
"""
```

- [ ] **Step 2: Remove pre-fetch logic**

Delete the stock data pre-fetch block (the `for s in stocks:` loop that calls `get_realtime`, `get_financial`, etc.). Keep only stock_list construction.

- [ ] **Step 3: Verify import**

```bash
cd backend && .venv/Scripts/python.exe -c "from app.main import app; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: agent mode — hermes curls data API instead of pre-fetch"
```

---

### Task 6: SkillManager Modal + Polish

**Files:**
- Modify: `frontend/src/components/SkillManager.tsx`

- [ ] **Step 1: Rewrite SkillManager with shadcn Dialog**

```typescript
import { useState, useEffect } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { listSkills, uploadSkill, deleteSkill } from '../api/skills'
import type { SkillMeta } from '../types'

interface Props { open: boolean; onClose: () => void; onRefresh: () => void }

export default function SkillManager({ open, onClose, onRefresh }: Props) {
  const [skills, setSkills] = useState<SkillMeta[]>([])
  useEffect(() => { if (open) listSkills().then(d => setSkills(d.skills)) }, [open])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]; if (!f) return
    await uploadSkill(f)
    const d = await listSkills(); setSkills(d.skills); onRefresh()
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader><DialogTitle>Skill 管理</DialogTitle></DialogHeader>
        {skills.map(s => (
          <div key={s.name} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <div>
              <div className="font-semibold text-sm">{s.name}</div>
              <div className="text-xs text-muted">{s.description || s.filename}</div>
            </div>
            <Button variant="destructive" size="sm" onClick={async () => { await deleteSkill(s.name); const d = await listSkills(); setSkills(d.skills); onRefresh() }}>
              删除
            </Button>
          </div>
        ))}
        {skills.length === 0 && <div className="text-center text-muted py-8">暂无 Skill，请导入</div>}
        <label className="block w-full">
          <Button variant="default" className="w-full" asChild>
            <span>导入 Skill (.md)</span>
          </Button>
          <input type="file" accept=".md" onChange={handleUpload} className="hidden" />
        </label>
      </DialogContent>
    </Dialog>
  )
}
```

Install: `npx shadcn@latest add dialog`

- [ ] **Step 2: Verify build + Commit**

```bash
npx tsc --noEmit
git add -A && git commit -m "feat: SkillManager with shadcn dialog"
```

---

### Task 7: Cleanup + Integration Verify

- [ ] **Step 1: Remove unused files**

```bash
rm frontend/src/App.css
rm frontend/src/components/ChatMessage.tsx
```

- [ ] **Step 2: Full build**

```bash
npx tsc --noEmit && npx vite build --logLevel error
```

- [ ] **Step 3: Backend verify**

```bash
cd /d/AI/hermesStockAgent/backend
.venv/Scripts/python.exe -c "
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
r = c.get('/api/v1/health')
assert r.status_code == 200 and 'tonghuashun' in r.json()['datasources']
print('PASS health')
r = c.get('/api/v1/search?q=600519')
assert len(r.json()['results']) > 0
print('PASS search')
r = c.get('/api/v1/skills')
assert r.status_code == 200
print('PASS skills')
print('ALL OK')
"
```

- [ ] **Step 4: Commit + Push**

```bash
git add -A && git commit -m "chore: cleanup, integration verification" && git push
```
