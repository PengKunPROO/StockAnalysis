# AI 诊断聊天面板重新设计 - 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重新设计 DiagnosisPanel 组件，实现结构化 SSE 事件分类、Skill toggle 开关、微信式聊天气泡布局。

**Architecture:** 后端 diagnosis.py 新增 `_classify_line` 行分类函数 + `ChatRequest.use_skill` 字段，SSE 事件改为 `{"type":"analysis|log|status|session|done|error", ...}`。前端 DiagnosisPanel.tsx 重写为标准聊天布局，SkillChip 替换 SkillPicker，diagnosis.ts 适配新事件结构只渲染 analysis 类型。

**Tech Stack:** FastAPI + Pydantic v2 (backend); React 19 + TypeScript (frontend); SSE streaming

## Global Constraints

- 后端入口 `backend/app/main.py:app`，端口 8002 不可更改
- Python 3.11，所有路由 handler 和 DB 操作必须 `async def`
- Pydantic v2 用于所有请求/响应模型
- 前端路径别名 `@/*` -> `./src/*`
- 暗黑科技风：`--bg:#0b1120`, `--accent:#06d6a0`, `--user-msg:#1e3a5f`, `--ai-msg:#111d31`
- `verify.sh` 检查 CSS class 和组件导入完整性
- Backend venv: `D:/AI/hermesStockAgent/backend/.venv`
- Frontend tsc: `cd D:/AI/hermesStockAgent/frontend && node node_modules/typescript/bin/tsc --noEmit`
- Backend tests: `cd D:/AI/hermesStockAgent/backend && D:/AI/hermesStockAgent/backend/.venv/Scripts/python -m pytest tests/ -v --tb=short`

---

## File Structure

```
backend/app/api/v1/diagnosis.py      # MODIFY: _classify_line + ChatRequest.use_skill + SSE
backend/tests/test_diagnosis.py      # MODIFY: add _classify_line unit tests
frontend/src/api/diagnosis.ts        # REWRITE: chatStream structured event handling
frontend/src/components/DiagnosisPanel.tsx  # REWRITE: SkillChip + chat bubbles + streaming
frontend/src/index.css               # MODIFY: add skill-chip styles
```

---

### Task 1: 后端 `_classify_line` 函数 + 单元测试

**Files:**
- Modify: `backend/app/api/v1/diagnosis.py`
- Test: `backend/tests/test_diagnosis.py`

**Interfaces:**
- Produces: `_classify_line(line: str) -> tuple[str, str | None]` — returns `("analysis"|"log"|"skip", content_or_None)`

- [ ] **Step 1: Write failing tests for `_classify_line`**

Add to `backend/tests/test_diagnosis.py`:

```python
from app.api.v1.diagnosis import _classify_line


class TestClassifyLine:
    def test_chinese_analysis_is_analysis(self):
        t, c = _classify_line("## 兆易创新技术分析报告")
        assert t == "analysis"
        assert c == "## 兆易创新技术分析报告"

    def test_markdown_table_is_analysis(self):
        t, c = _classify_line("| 指标 | 数值 |")
        assert t == "analysis"

    def test_chinese_list_is_analysis(self):
        t, c = _classify_line("- MACD指标：-54.82，空头排列")
        assert t == "analysis"

    def test_number_with_percent_is_analysis(self):
        t, c = _classify_line("涨跌幅 -2.09%")
        assert t == "analysis"

    def test_curl_command_is_log(self):
        t, c = _classify_line('curl -s --max-time 15 "http://localhost:8002/api/v1/stock/sh.600519/realtime"')
        assert t == "log"
        assert "curl" in c

    def test_file_path_is_log(self):
        t, c = _classify_line("Remote: `git@github.com:PengKunPROO/StockAnalysis.git`")
        assert t == "log"

    def test_project_root_is_log(self):
        t, c = _classify_line("Project root: `D:\\AI\\hermesStockAgent`")
        assert t == "log"

    def test_code_block_delimiter_is_log(self):
        t, c = _classify_line("```python")
        assert t == "log"

    def test_import_statement_is_log(self):
        t, c = _classify_line("import asyncio")
        assert t == "log"

    def test_empty_line_is_skip(self):
        t, c = _classify_line("")
        assert t == "skip"
        assert c is None

    def test_whitespace_only_is_skip(self):
        t, c = _classify_line("   \t  ")
        assert t == "skip"

    def test_session_marker_is_skip(self):
        t, c = _classify_line("Session: 20260715_010356_0e8c45")
        assert t == "skip"

    def test_duration_is_skip(self):
        t, c = _classify_line("Duration: 45.2s")
        assert t == "skip"

    def test_hermes_resume_is_skip(self):
        t, c = _classify_line("hermes --resume 20260715_010356_0e8c45")
        assert t == "skip"

    def test_box_drawing_is_skip(self):
        t, c = _classify_line("╭──────────────────╮")
        assert t == "skip"

    def test_pure_english_heading_is_log(self):
        """English-only ### headings are skill echo, not analysis."""
        t, c = _classify_line("### What NOT to push")
        assert t == "log"

    def test_mixed_chinese_english_is_analysis(self):
        t, c = _classify_line("## 兆易创新 (sh.603986) 综合分析")
        assert t == "analysis"

    def test_mongodb_config_line_is_log(self):
        t, c = _classify_line("name: hermesstockagent-workflow")
        assert t == "log"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/AI/hermesStockAgent/backend && D:/AI/hermesStockAgent/backend/.venv/Scripts/python -m pytest tests/test_diagnosis.py::TestClassifyLine -v --tb=short`
Expected: FAIL with ImportError (`_classify_line` not defined)

- [ ] **Step 3: Implement `_classify_line` in `diagnosis.py`**

Add this function after the existing `_filter_line` function (around line 51), before `_resolve_hermes_binary`:

```python
import re as _re

LOG_PATTERNS = [
    _re.compile(r'^curl\s'),
    _re.compile(r'^Remote:'),
    _re.compile(r'^Project root:'),
    _re.compile(r'^import\s'),
    _re.compile(r'^pip\s'),
    _re.compile(r'^npm\s'),
    _re.compile(r'^```\w*'),
    _re.compile(r'^name:'),
    _re.compile(r'^description:'),
    _re.compile(r'^mode:'),
    _re.compile(r'^[A-Z][a-z]+:'),  # "Key:" style config lines
    # English-only ### headings (skill echo): no CJK chars
    _re.compile(r'^#+\s+[A-Za-z][A-Za-z\s,/()\-:]+$'),
]

CLASSIFY_SKIP_PATTERNS = [
    _re.compile(r'^Query:'),
    _re.compile(r'^Initializing agent'),
    _re.compile(r'^[─╭╰═╮╯┊]+'),
    _re.compile(r'^Resume this session'),
    _re.compile(r'^Session:'),
    _re.compile(r'^Duration:'),
    _re.compile(r'^Messages:'),
    _re.compile(r'^---'),
    _re.compile(r'^hermes --resume'),
    _re.compile(r'^\s*┊\s'),
    _re.compile(r'^\s*$'),
]

# CJK Unicode range check
def _has_cjk(text: str) -> bool:
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f':
            return True
    return False


def _classify_line(line: str) -> tuple[str, str | None]:
    """Classify a hermes output line as analysis, log, or skip."""
    clean = ANSI_RE.sub('', line).rstrip('\n')
    # Skip
    for pat in CLASSIFY_SKIP_PATTERNS:
        if pat.match(clean):
            return "skip", None
    # Log
    for pat in LOG_PATTERNS:
        if pat.match(clean):
            return "log", clean
    # Empty after strip
    if not clean.strip():
        return "skip", None
    # Everything else is analysis
    return "analysis", clean
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:/AI/hermesStockAgent/backend && D:/AI/hermesStockAgent/backend/.venv/Scripts/python -m pytest tests/test_diagnosis.py::TestClassifyLine -v --tb=short`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd D:/AI/hermesStockAgent
git add backend/app/api/v1/diagnosis.py backend/tests/test_diagnosis.py
git commit -m "feat: add _classify_line for SSE event classification (analysis/log/skip)"
```

---

### Task 2: 后端 ChatRequest.use_skill + SSE 结构化事件

**Files:**
- Modify: `backend/app/api/v1/diagnosis.py`

**Interfaces:**
- Consumes: `_classify_line` from Task 1
- Produces: SSE events with `{"type":"analysis|log|status|session|done|error", ...}` format
- Produces: `ChatRequest.use_skill: bool = True` field

- [ ] **Step 1: Add `use_skill` field to ChatRequest**

In `backend/app/api/v1/diagnosis.py`, modify the ChatRequest class:

```python
class ChatRequest(BaseModel):
    session_id: str | None = None
    skill: str = "stock-analysis"
    use_skill: bool = True
    message: str
    stock_codes: list[dict] | None = None
```

- [ ] **Step 2: Make skill injection conditional on `use_skill`**

In the `chat()` function, replace the `skill_content` line:

```python
    skill_content = ""
    if req.use_skill and req.skill:
        skill_content = _resolve_skill_content(req.skill)
```

- [ ] **Step 3: Replace SSE event_stream with structured events**

Replace the entire `event_stream` function body (from `async def event_stream():` to the `yield f"data: {json.dumps({'done': True}...` line) with:

```python
    async def event_stream():
        yield f'data: {json.dumps({"type":"session","session_id": sid}, ensure_ascii=False)}\n\n'
        yield f'data: {json.dumps({"type":"status","status":"agent_starting"}, ensure_ascii=False)}\n\n'

        queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=1)
        ready_event = asyncio.Event()
        loop.run_in_executor(executor, _read_subprocess, prompt, queue, ready_event)

        full_output = ""
        returncode = 0
        stderr_text = ""

        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                continue

            if item is None:
                break
            if isinstance(item, Exception):
                yield f'data: {json.dumps({"type":"error","content": f"Error: {item}"}, ensure_ascii=False)}\n\n'
                yield f'data: {json.dumps({"type":"done"}, ensure_ascii=False)}\n\n'
                executor.shutdown(wait=False)
                return

            line = item if isinstance(item, str) else str(item)
            event_type, content = _classify_line(line)

            if event_type == "skip":
                continue
            elif event_type == "log":
                if "curl" in content:
                    yield f'data: {json.dumps({"type":"status","status":"fetching_data"}, ensure_ascii=False)}\n\n'
                yield f'data: {json.dumps({"type":"log","content": content}, ensure_ascii=False)}\n\n'
            elif event_type == "analysis":
                full_output += content + "\n"
                yield f'data: {json.dumps({"type":"analysis","content": content + "\n"}, ensure_ascii=False)}\n\n'

        # Read final signals
        try:
            returncode = await asyncio.wait_for(queue.get(), timeout=5.0)
            stderr_text = await asyncio.wait_for(queue.get(), timeout=5.0)
        except (asyncio.TimeoutError, Exception):
            returncode = -1
            stderr_text = ""

        executor.shutdown(wait=True)

        if returncode != 0:
            err = stderr_text or f"Hermes exited with code {returncode}"
            yield f'data: {json.dumps({"type":"error","content": f"Agent Error: {err}"}, ensure_ascii=False)}\n\n'
            yield f'data: {json.dumps({"type":"done"}, ensure_ascii=False)}\n\n'
            return

        await save_message(sid, "user", content=req.message)
        await save_message(sid, "assistant", content=full_output.strip())
        yield f'data: {json.dumps({"type":"done"}, ensure_ascii=False)}\n\n'
```

- [ ] **Step 4: Run existing tests to verify no regression**

Run: `cd D:/AI/hermesStockAgent/backend && D:/AI/hermesStockAgent/backend/.venv/Scripts/python -m pytest tests/test_diagnosis.py -v --tb=short`
Expected: Existing skipped tests still skip, `_classify_line` tests still pass

- [ ] **Step 5: Commit**

```bash
cd D:/AI/hermesStockAgent
git add backend/app/api/v1/diagnosis.py
git commit -m "feat: structured SSE events (type=analysis/log/status/session/done/error) + use_skill toggle"
```

---

### Task 3: 前端 diagnosis.ts 适配结构化 SSE

**Files:**
- Modify: `frontend/src/api/diagnosis.ts`

**Interfaces:**
- Consumes: SSE events with `{"type":"analysis|log|status|session|done|error", ...}`
- Produces: `chatStream()` with typed callbacks including `onLog`
- Produces: `ChatParams.use_skill: boolean`

- [ ] **Step 1: Rewrite `diagnosis.ts`**

Replace the entire file content:

```typescript
interface ChatParams {
  session_id?: string
  skill: string
  use_skill: boolean
  message: string
  stock_codes: { code: string; name: string }[]
}

interface ChatEvents {
  onSessionId?: (id: string) => void
  onStatus?: (status: string) => void
  onContent?: (chunk: string) => void
  onLog?: (chunk: string) => void
  onDone?: () => void
  onError?: (err: string) => void
}

export async function chatStream(params: ChatParams, events: ChatEvents) {
  try {
    const res = await fetch('/api/v1/diagnosis/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })
    if (!res.ok) {
      events.onError?.(`HTTP ${res.status}`)
      return
    }
    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const data = JSON.parse(line.slice(6))
          switch (data.type) {
            case 'session': events.onSessionId?.(data.session_id); break
            case 'status': events.onStatus?.(data.status); break
            case 'analysis': events.onContent?.(data.content || ''); break
            case 'log': events.onLog?.(data.content || ''); break
            case 'error': events.onError?.(data.content || 'Unknown error'); break
            case 'done': events.onDone?.(); break
          }
        } catch {}
      }
    }
  } catch (e: any) {
    events.onError?.(e.message || 'Connection error')
  }
}
```

- [ ] **Step 2: Run tsc to verify**

Run: `cd D:/AI/hermesStockAgent/frontend && node node_modules/typescript/bin/tsc --noEmit`
Expected: 0 errors

- [ ] **Step 3: Commit**

```bash
cd D:/AI/hermesStockAgent
git add frontend/src/api/diagnosis.ts
git commit -m "feat: diagnosis.ts structured SSE event handling (type-based dispatch)"
```

---

### Task 4: 前端 DiagnosisPanel.tsx 重写 + CSS

**Files:**
- Modify: `frontend/src/components/DiagnosisPanel.tsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Consumes: `chatStream` with `use_skill` param + `onLog` callback from Task 3
- Consumes: `state.skills`, `state.currentStock` from AppContext

- [ ] **Step 1: Add skill-chip CSS to `index.css`**

Add these styles after the existing `.skill-opt .stag.uploaded` rule (around line 274):

```css
/* === Skill Chip (toggle + dropdown) === */
.skill-chip { display: flex; align-items: center; gap: 8px; padding: 5px 12px; border-radius: 20px; border: 1px solid var(--border); background: var(--surface2); cursor: pointer; transition: .2s; user-select: none; }
.skill-chip:hover { border-color: var(--accent); background: var(--accent-glow); }
.skill-chip.active { border-color: var(--accent); background: var(--accent-glow); }
.skill-chip-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--muted); transition: .2s; flex-shrink: 0; }
.skill-chip.active .skill-chip-dot { background: var(--accent); box-shadow: 0 0 6px var(--accent); }
.skill-chip-name { font-size: 0.72rem; color: var(--heading); max-width: 130px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 500; }
.skill-chip.active .skill-chip-name { color: var(--accent); }
.skill-chip-name.unset { color: var(--muted); font-style: italic; }
.skill-chip-caret { font-size: 0.6rem; color: var(--muted); margin-left: 2px; transition: .2s; }
.skill-chip:hover .skill-chip-caret { color: var(--accent); }

/* Skill dropdown refined */
.skill-dropdown { position: absolute; top: calc(100% + 6px); right: 0; width: 320px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; z-index: 300; box-shadow: 0 12px 32px rgba(0,0,0,.5); overflow: hidden; display: none; animation: dropdownIn .15s; }
@keyframes dropdownIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
.skill-dropdown.open { display: block; }
.skill-search-wrap { padding: 10px 12px; border-bottom: 1px solid var(--border); position: relative; }
.skill-search { width: 100%; padding: 7px 12px 7px 30px; border-radius: 8px; border: 1px solid var(--border); background: var(--surface2); color: var(--heading); font-size: 0.78rem; outline: none; transition: .2s; }
.skill-search:focus { border-color: var(--accent); }
.skill-search-icon { position: absolute; left: 22px; top: 50%; transform: translateY(-50%); font-size: 0.7rem; color: var(--muted); pointer-events: none; }
```

- [ ] **Step 2: Rewrite `DiagnosisPanel.tsx`**

Replace the entire file:

```tsx
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
```

- [ ] **Step 3: Run tsc to verify**

Run: `cd D:/AI/hermesStockAgent/frontend && node node_modules/typescript/bin/tsc --noEmit`
Expected: 0 errors

- [ ] **Step 4: Verify CSS classes exist**

Ensure `index.css` still has `.chat-panel`, `.chat-header`, `.chat-messages`, `.chat-empty`, `.chat-status`, `.chat-input`, `.msg`, `.msg.user`, `.msg.ai`, `.msg-system`, `.msg-body`, `.msg-user-text`, `.md-table`, `.md-p`, `.md-ul`, `.md-ol`, `.md-li`, `.md-strong`, `.md-link`, `.md-hr`, `.md-quote`, `.md-code-block`, `.md-inline-code`, `.md-h1`, `.md-h2`, `.md-h3`, `.md-h4`, `.skill-opt`, `.skill-list`, `.sn`, `.sd`, `.stag`, `.stag.hermes`, `.stag.uploaded`, `.icon-btn`, `.title`, `.hint`, `.dot` classes. These should already exist from the original CSS.

- [ ] **Step 5: Commit**

```bash
cd D:/AI/hermesStockAgent
git add frontend/src/components/DiagnosisPanel.tsx frontend/src/index.css
git commit -m "feat: rewrite DiagnosisPanel - SkillChip toggle, WeChat-style bubbles, structured SSE rendering"
```

---

### Task 5: 集成验证 + 最终提交

**Files:**
- All modified files from Tasks 1-4

- [ ] **Step 1: Run full backend test suite**

Run: `cd D:/AI/hermesStockAgent/backend && D:/AI/hermesStockAgent/backend/.venv/Scripts/python -m pytest tests/ -v --tb=short`
Expected: All tests pass (including new `TestClassifyLine` tests, existing portfolio tests)

- [ ] **Step 2: Run tsc**

Run: `cd D:/AI/hermesStockAgent/frontend && node node_modules/typescript/bin/tsc --noEmit`
Expected: 0 errors

- [ ] **Step 3: Run verify.sh**

Run: `cd D:/AI/hermesStockAgent && bash verify.sh`
Expected: All 4 checks pass (pytest, tsc+build, integrity, port)

- [ ] **Step 4: Push all commits**

```bash
cd D:/AI/hermesStockAgent
git push
```
