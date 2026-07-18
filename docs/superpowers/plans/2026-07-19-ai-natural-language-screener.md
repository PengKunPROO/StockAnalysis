# AI 自然语言选股系统 - 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在选股器 Tab 里加 AI 辅助选股功能，用户输入自然语言意图，hermes 子进程结合 skill 调 API 筛选股票，SSE 流式返回候选列表。

**Architecture:** 后端新增 `POST /screener/ai-scan` SSE 端点，复用 diagnosis.py 的 hermes 子进程 + `_classify_line` 分类逻辑。前端新增 `AIScreenerPanel.tsx`，嵌入 ScreenerView 顶部，复用 SkillChip 和 chatStream。3 个内置选股 skill 文件放在 `backend/skills/`。

**Tech Stack:** FastAPI + Pydantic v2 (backend); React 19 + TypeScript (frontend); hermes 子进程 + SSE streaming

## Global Constraints

- 后端入口 `backend/app/main.py:app`，端口 8002 不可更改
- Python 3.11，所有路由 handler 和 DB 操作必须 `async def`
- Pydantic v2 用于所有请求/响应模型
- 前端路径别名 `@/*` -> `./src/*`
- 暗黑科技风：`--bg:#0b1120`, `--accent:#06d6a0`
- Backend venv: `D:/AI/hermesStockAgent/backend/.venv`
- Frontend tsc: `cd D:/AI/hermesStockAgent/frontend && node node_modules/typescript/bin/tsc --noEmit`
- Backend tests: `cd D:/AI/hermesStockAgent/backend && D:/AI/hermesStockAgent/backend/.venv/Scripts/python -m pytest tests/ -v --tb=short`
- hermes 子进程通过 `subprocess.Popen` 启动，env 设 `NO_COLOR=1`
- SSE 事件结构：`{"type":"session|status|analysis|log|error|done", ...}`
- skill 内容通过 `_resolve_skill_content()` 解析（先 backend/skills/ 上传，再 hermes 全局 skill）

---

## File Structure

```
backend/app/api/v1/screener.py           # MODIFY: 新增 /ai-scan SSE 端点
backend/skills/                           # CREATE: 内置选股 skill 目录
│   ├── oversold-bounce.md               # 超跌反弹选股
│   ├── value-discovery.md               # 价值发现选股
│   └── breakout-screener.md             # 技术突破选股
backend/tests/test_screener.py           # MODIFY: 新增 ai-scan 测试
frontend/src/api/screener.ts              # MODIFY: 新增 aiScan SSE 函数
frontend/src/components/AIScreenerPanel.tsx  # CREATE: AI 选股面板
frontend/src/components/ScreenerView.tsx  # MODIFY: 嵌入 AIScreenerPanel
frontend/src/index.css                    # MODIFY: AI 选股区域样式
```

---

### Task 1: 后端 AI 选股 SSE 端点

**Files:**
- Modify: `backend/app/api/v1/screener.py`
- Test: `backend/tests/test_screener.py`

**Interfaces:**
- Consumes: `_resolve_skill_content`, `_classify_line`, `_resolve_hermes_binary`, `_read_subprocess`, `_shell_quote` from `diagnosis.py`
- Produces: `POST /api/v1/screener/ai-scan` SSE endpoint

- [ ] **Step 1: Write failing test for ai-scan endpoint**

Add to `backend/tests/test_screener.py`:

```python
from unittest.mock import AsyncMock, patch, MagicMock
import json


class TestAIScan:
    def test_ai_scan_returns_sse_stream(self, client):
        """AI scan should return SSE text/event-stream."""
        with patch("app.api.v1.screener._read_subprocess") as mock_sub:
            # Simulate hermes output
            def fake_read(prompt, queue, ready_event):
                ready_event.set()
                queue.put_nowait("## 选股分析\n")
                queue.put_nowait("根据您的意图，我筛选出以下股票：\n")
                queue.put_nowait(None)
                queue.put_nowait(0)
                queue.put_nowait("")
            mock_sub.side_effect = fake_read

            resp = client.post("/api/v1/screener/ai-scan", json={
                "message": "找超跌反弹股",
                "skill": "",
                "use_skill": False,
            })
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        # Should contain SSE events
        assert "data:" in resp.text
        assert '"type"' in resp.text

    def test_ai_scan_with_skill(self, client):
        """AI scan with skill should include skill content in prompt."""
        with patch("app.api.v1.screener._read_subprocess") as mock_sub:
            captured_prompt = []
            def fake_read(prompt, queue, ready_event):
                ready_event.set()
                captured_prompt.append(prompt)
                queue.put_nowait("分析完成\n")
                queue.put_nowait(None)
                queue.put_nowait(0)
                queue.put_nowait("")
            mock_sub.side_effect = fake_read

            with patch("app.api.v1.screener._resolve_skill_content", return_value="## 超跌反弹策略\nRSI<30"):
                resp = client.post("/api/v1/screener/ai-scan", json={
                    "message": "找超跌股",
                    "skill": "oversold-bounce",
                    "use_skill": True,
                })
        assert resp.status_code == 200
        assert "RSI<30" in captured_prompt[0]

    def test_ai_scan_without_skill(self, client):
        """AI scan with use_skill=False should NOT include skill content."""
        with patch("app.api.v1.screener._read_subprocess") as mock_sub:
            captured_prompt = []
            def fake_read(prompt, queue, ready_event):
                ready_event.set()
                captured_prompt.append(prompt)
                queue.put_nowait("分析完成\n")
                queue.put_nowait(None)
                queue.put_nowait(0)
                queue.put_nowait("")
            mock_sub.side_effect = fake_read

            resp = client.post("/api/v1/screener/ai-scan", json={
                "message": "找超跌股",
                "skill": "oversold-bounce",
                "use_skill": False,
            })
        assert resp.status_code == 200
        assert "超跌反弹策略" not in captured_prompt[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/AI/hermesStockAgent/backend && D:/AI/hermesStockAgent/backend/.venv/Scripts/python -m pytest tests/test_screener.py::TestAIScan -v --tb=short`
Expected: FAIL (no /ai-scan endpoint)

- [ ] **Step 3: Implement the ai-scan endpoint in screener.py**

Add these imports at the top of `backend/app/api/v1/screener.py`:

```python
from fastapi.responses import StreamingResponse
from fastapi import APIRouter, Query
from pydantic import BaseModel
import asyncio, json, os, subprocess
from concurrent.futures import ThreadPoolExecutor
from app.api.v1.diagnosis import (
    _resolve_skill_content, _classify_line,
    _resolve_hermes_binary, _read_subprocess, _shell_quote,
)
```

Add the request model and endpoint after the existing `/run` endpoint:

```python
class AIScanRequest(BaseModel):
    message: str
    skill: str = ""
    use_skill: bool = True
    stock_codes: list[dict] = []


@router.post("/ai-scan")
async def ai_scan(req: AIScanRequest):
    skill_content = ""
    if req.use_skill and req.skill:
        skill_content = _resolve_skill_content(req.skill)

    stock_list = ", ".join(f"{s.get('name','')}({s.get('code','')})" for s in req.stock_codes) if req.stock_codes else "全市场"

    prompt = f"""{skill_content}

你是 A 股选股 Agent。可以通过终端运行 curl 获取数据。后端运行在 localhost:8002。

## 可用数据 API (每次 curl 加 --max-time 15):
- 全市场快照: curl -s --max-time 15 "http://localhost:8002/api/v1/intelligence/overview"
- 选股器: curl -s --max-time 15 -X POST "http://localhost:8002/api/v1/screener/run" -H "Content-Type: application/json" -d '{{"fields":{{"rsi_oversold":true}},"limit":20}}'
- K线: curl -s --max-time 15 "http://localhost:8002/api/v1/stock/<代码>/kline?period=daily&start=YYYY-MM-DD&end=YYYY-MM-DD"
- 实时: curl -s --max-time 15 "http://localhost:8002/api/v1/stock/<代码>/realtime"
- 财务: curl -s --max-time 15 "http://localhost:8002/api/v1/stock/<代码>/financial"
- 指标: curl -s --max-time 15 "http://localhost:8002/api/v1/stock/<代码>/indicators?days=60"
- 涨停池: curl -s --max-time 15 "http://localhost:8002/api/v1/intelligence/limit-up"
- 龙虎榜: curl -s --max-time 15 "http://localhost:8002/api/v1/intelligence/dragon-tiger"
- 热榜: curl -s --max-time 15 "http://localhost:8002/api/v1/intelligence/fund-flow"

## 选股器 fields 参数说明 (JSON):
可用因子:
- change_pct: 涨跌幅(%)
- amount: 成交额(元), 1亿=100000000
- amplitude: 振幅(%)
- rsi_oversold: RSI超卖(boolean true)
- macd_golden_cross: MACD金叉(boolean true)
- boll_breakout: 布林突破(boolean true)
- roe: ROE(%)
- debt_ratio: 负债率(%)
- near_high_drop: 距52周高点跌幅(%)
- change_5d: 5日涨跌幅(%)
- change_20d: 20日涨跌幅(%)
- on_dragon_tiger: 龙虎榜上榜(boolean true)

示例:
curl -s --max-time 15 -X POST "http://localhost:8002/api/v1/screener/run" \\
  -H "Content-Type: application/json" \\
  -d '{{"fields":{{"rsi_oversold":true,"near_high_drop":{{"min":30}},"amount":{{"min":100000000}}}},"limit":20}}'

## 规则:
1. 分析用户意图，确定需要哪些筛选因子
2. 如果有 skill，优先参考 skill 中的选股逻辑和阈值建议
3. 先用选股器 API 粗筛，再对结果逐个 curl 获取详细数据
4. 每只候选股票给出入选理由（技术面/基本面/消息面）
5. 返回 5-15 只候选股票，按推荐度排序
6. 不编造数据，curl 失败明确说明
7. 排除 ST 股、退市风险股

## 输出格式:
先用 Markdown 列出分析过程，最后输出候选股票表格:
| 代码 | 名称 | 现价 | 涨跌幅 | 入选理由 |
|------|------|------|--------|----------|
然后给出整体分析和操作建议。

## 当前标的范围: {stock_list}

用户意图: {req.message}
"""

    async def event_stream():
        yield f'data: {json.dumps({"type":"status","status":"agent_starting"}, ensure_ascii=False)}\n\n'

        queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=1)
        ready_event = asyncio.Event()
        loop.run_in_executor(executor, _read_subprocess, prompt, queue, ready_event)

        full_output = ""
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
                if content and "curl" in content:
                    yield f'data: {json.dumps({"type":"status","status":"fetching_data"}, ensure_ascii=False)}\n\n'
                yield f'data: {json.dumps({"type":"log","content": content}, ensure_ascii=False)}\n\n'
            elif event_type == "analysis":
                full_output += content + "\n"
                yield f'data: {json.dumps({"type":"analysis","content": content + "\n"}, ensure_ascii=False)}\n\n'

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

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:/AI/hermesStockAgent/backend && D:/AI/hermesStockAgent/backend/.venv/Scripts/python -m pytest tests/test_screener.py::TestAIScan -v --tb=short`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd D:/AI/hermesStockAgent
git add backend/app/api/v1/screener.py backend/tests/test_screener.py
git commit -m "feat: add POST /screener/ai-scan SSE endpoint for AI natural language stock screening"
```

---

### Task 2: 内置选股 Skill 文件

**Files:**
- Create: `backend/skills/oversold-bounce.md`
- Create: `backend/skills/value-discovery.md`
- Create: `backend/skills/breakout-screener.md`

**Interfaces:**
- Produces: 3 skill files readable by `_resolve_skill_content()` via `skills_manager.get_skill_content()`

- [ ] **Step 1: Create oversold-bounce.md**

```markdown
---
name: oversold-bounce
description: 超跌反弹选股策略。当用户寻找超跌反弹、短线抄底、RSI超卖、跌幅过大的股票时使用此技能。
mode: analysis
---

# 超跌反弹选股策略

## 核心逻辑
寻找短期跌幅过大、技术面超卖、但基本面稳健的股票，博弈技术性反弹。

## 筛选条件

### 技术面（必须满足至少2项）
- RSI(14) < 30（超卖区域）
- 距52周高点跌幅 > 30%（near_high_drop >= 30）
- 5日跌幅 < -5%（change_5d <= -5）
- 价格接近布林下轨

### 基本面（排除垃圾股）
- ROE > 5%（确保公司有基本盈利能力）
- 负债率 < 70%（排除高杠杆风险）
- 排除 ST、*ST 股票

### 流动性
- 成交额 > 1亿元（amount >= 100000000）

## 执行步骤
1. 用选股器粗筛：`{"rsi_oversold": true, "near_high_drop": {"min": 30}, "amount": {"min": 100000000}}`
2. 对结果逐个查财务：ROE > 5%，负债率 < 70%
3. 检查是否有龙虎榜机构买入（利好信号）
4. 按跌幅排序，跌幅越大且基本面越好的优先推荐

## 输出要求
每只股票说明：当前跌幅、RSI值、ROE、入选理由（为什么认为会反弹）
```

- [ ] **Step 2: Create value-discovery.md**

```markdown
---
name: value-discovery
description: 价值发现选股策略。当用户寻找低估值、高ROE、基本面强劲的价值股、长线布局时使用此技能。
mode: analysis
---

# 价值发现选股策略

## 核心逻辑
寻找基本面优秀但市场暂未充分定价的股票，适合中长期布局。

## 筛选条件

### 基本面（核心）
- ROE > 15%（高回报）
- 负债率 < 50%（低杠杆）
- 营收稳定增长（通过财务数据对比多期）

### 技术面（辅助）
- 近20日涨跌幅在 -10% 到 +5% 之间（未大涨也未暴跌）
- MACD 接近金叉或已金叉
- 成交额 > 2亿元（机构关注度高）

### 排除条件
- 排除周期股顶部特征（近20日涨幅 > 20%）
- 排除 ST、*ST 股票

## 执行步骤
1. 用选股器粗筛：`{"roe": {"min": 15}, "debt_ratio": {"max": 50}, "amount": {"min": 200000000}}`
2. 对结果逐个查财务报表：确认营收和利润是否持续增长
3. 检查近期是否有利好公告或龙虎榜机构买入
4. 按 ROE 从高到低排序

## 输出要求
每只股票说明：ROE、负债率、营收增速、近期资金动向、入选理由
```

- [ ] **Step 3: Create breakout-screener.md**

```markdown
---
name: breakout-screener
description: 技术突破选股策略。当用户寻找技术面突破、放量上涨、MACD金叉、布林突破的股票时使用此技能。
mode: analysis
---

# 技术突破选股策略

## 核心逻辑
寻找技术面出现突破信号的股票，博弈趋势延续。

## 筛选条件

### 技术面（必须满足至少2项）
- MACD 金叉（macd_golden_cross: true）
- 布林带突破上轨（boll_breakout: true）
- 涨幅 > 3%（change_pct >= 3，确认突破力度）
- 振幅 > 5%（amplitude >= 5，活跃度高）

### 量能确认
- 成交额 > 3亿元（amount >= 300000000，放量突破）
- 换手率适中（非一字涨停）

### 排除条件
- 排除连续涨停 > 3 板的股票（追高风险大）
- 排除 ST、*ST 股票
- 排除近5日涨幅 > 30% 的股票（已涨太多）

## 执行步骤
1. 用选股器粗筛：`{"change_pct": {"min": 3}, "amplitude": {"min": 5}, "amount": {"min": 300000000}, "boll_breakout": true}`
2. 检查 MACD 是否金叉
3. 查看龙虎榜是否有机构/游资买入
4. 检查热榜排名（热度上升 = 市场关注）
5. 按成交额排序，量能越大越优先

## 输出要求
每只股票说明：涨幅、振幅、成交额、MACD状态、布林状态、龙虎榜情况、入选理由
```

- [ ] **Step 4: Verify skills load correctly**

Run: `cd D:/AI/hermesStockAgent/backend && D:/AI/hermesStockAgent/backend/.venv/Scripts/python -c "from app.diagnosis.skills_manager import get_skill_content; print('oversold:', bool(get_skill_content('oversold-bounce'))); print('value:', bool(get_skill_content('value-discovery'))); print('breakout:', bool(get_skill_content('breakout-screener')))"`
Expected: all True

- [ ] **Step 5: Commit**

```bash
cd D:/AI/hermesStockAgent
git add backend/skills/
git commit -m "feat: add 3 built-in screener skills (oversold-bounce, value-discovery, breakout-screener)"
```

---

### Task 3: 前端 AI 选股 API + 组件

**Files:**
- Modify: `frontend/src/api/screener.ts`
- Create: `frontend/src/components/AIScreenerPanel.tsx`
- Modify: `frontend/src/components/ScreenerView.tsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Consumes: `chatStream` pattern from `diagnosis.ts` (SSE handling)
- Consumes: `SkillChip` component pattern from `DiagnosisPanel.tsx`
- Consumes: `state.skills` from AppContext

- [ ] **Step 1: Add aiScan function to screener.ts**

Add to the end of `frontend/src/api/screener.ts`:

```typescript
// AI Natural Language Screening (SSE stream)
interface AIScanParams {
  message: string
  skill: string
  use_skill: boolean
  stock_codes?: { code: string; name: string }[]
}

interface AIScanEvents {
  onStatus?: (status: string) => void
  onContent?: (chunk: string) => void
  onLog?: (chunk: string) => void
  onDone?: () => void
  onError?: (err: string) => void
}

export async function aiScan(params: AIScanParams, events: AIScanEvents) {
  try {
    const res = await fetch('/api/v1/screener/ai-scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })
    if (!res.ok) { events.onError?.(`HTTP ${res.status}`); return }
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

- [ ] **Step 2: Create AIScreenerPanel.tsx**

Create `frontend/src/components/AIScreenerPanel.tsx`:

```tsx
import { useState, useRef, useEffect, memo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useApp } from '../contexts/AppContext'
import { aiScan } from '../api/screener'
import type { SkillMeta } from '../types'

const MemoMarkdown = memo(function MD({ content }: { content: string }) {
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
        p: ({ children }) => <p className="md-p">{children}</p>,
        strong: ({ children }) => <strong className="md-strong">{children}</strong>,
      }}>
        {content}
      </ReactMarkdown>
    </div>
  )
})

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

  return (
    <div ref={ref} style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
      <div className={`skill-chip ${useSkill ? 'active' : ''}`} onClick={(e) => { e.stopPropagation(); onToggle() }}>
        <div className="skill-chip-dot" />
        <span className={`skill-chip-name ${!skill ? 'unset' : ''}`} onClick={(e) => { e.stopPropagation(); setOpen(!open); setTimeout(() => inputRef.current?.focus(), 50) }}>
          {skill || '选股 Skill'}
        </span>
        <span className="skill-chip-caret" onClick={(e) => { e.stopPropagation(); setOpen(!open); setTimeout(() => inputRef.current?.focus(), 50) }}>▼</span>
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
                <div><span className="sn">{s.name}</span></div>
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

export default function AIScreenerPanel() {
  const { state } = useApp()
  const [input, setInput] = useState('')
  const [result, setResult] = useState('')
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState('')
  const [skill, setSkill] = useState('')
  const [useSkill, setUseSkill] = useState(true)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [result])

  const run = async () => {
    if (!input.trim() || loading) return
    const text = input.trim()
    setLoading(true); setResult(''); setStatus('agent_starting')
    let full = ''
    await aiScan({
      message: text, skill, use_skill: useSkill,
      stock_codes: state.currentStock ? [{ code: state.currentStock.code, name: state.currentStock.name }] : [],
    }, {
      onStatus: s => setStatus(s),
      onContent: c => { full += c; setResult(full); setStatus('') },
      onLog: () => { if (!status) setStatus('fetching_data') },
      onDone: () => { setLoading(false); setStatus('') },
      onError: e => { setResult(`Error: ${e}`); setLoading(false); setStatus('') },
    })
  }

  const statusText: Record<string, string> = { agent_starting: 'Agent 启动中...', fetching_data: '获取数据中...' }

  return (
    <div className="ai-screener-panel">
      <div className="ai-screener-header">
        <span className="title">🔍 AI 选股</span>
        <span style={{ flex: 1 }} />
        <SkillChip
          skills={state.skills}
          skill={skill}
          useSkill={useSkill}
          onToggle={() => setUseSkill(v => !v)}
          onPick={setSkill}
        />
      </div>
      <div className="ai-screener-input">
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); run() } }}
          placeholder='输入选股意图，如"找超跌反弹股，基本面要好"...'
          disabled={loading}
          rows={2}
        />
        <button onClick={run} disabled={loading || !input.trim()}>
          {loading ? '分析中...' : '开始选股'}
        </button>
      </div>
      {(loading || status) && (
        <div className="chat-status">
          <span className="dot" /> {statusText[status] || status || '处理中...'}
        </div>
      )}
      {result && (
        <div className="ai-screener-result">
          <MemoMarkdown content={result} />
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Add CSS styles to index.css**

Add to the end of `frontend/src/index.css`:

```css
/* === AI Screener Panel === */
.ai-screener-panel { background: var(--surface); border: 1px solid var(--border-light); border-radius: 8px; margin-bottom: 12px; overflow: hidden; flex-shrink: 0; }
.ai-screener-header { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-bottom: 1px solid var(--border); }
.ai-screener-header .title { font-size: clamp(0.85rem, 1.1vw, 0.95rem); font-weight: 700; color: var(--heading); }
.ai-screener-input { display: flex; gap: 8px; padding: 10px 14px; border-bottom: 1px solid var(--border); }
.ai-screener-input textarea { flex: 1; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--border); background: var(--surface2); color: var(--heading); font-size: clamp(0.75rem, 1vw, 0.85rem); resize: none; outline: none; min-height: 36px; max-height: 120px; font-family: var(--font); transition: border-color .2s; }
.ai-screener-input textarea:focus { border-color: var(--accent); }
.ai-screener-input button { padding: 6px 16px; border-radius: 8px; border: none; background: var(--accent); color: #000; font-weight: 600; font-size: clamp(0.75rem, 1vw, 0.85rem); cursor: pointer; white-space: nowrap; }
.ai-screener-input button:hover { filter: brightness(1.1); }
.ai-screener-input button:disabled { opacity: .4; cursor: default; }
.ai-screener-result { padding: 12px 14px; max-height: 500px; overflow-y: auto; }
```

- [ ] **Step 4: Embed AIScreenerPanel in ScreenerView**

In `frontend/src/components/ScreenerView.tsx`, add import at the top:

```typescript
import AIScreenerPanel from './AIScreenerPanel'
```

Add the component at the very beginning of the return, before the existing screener UI:

```tsx
  return (
    <div className="screener-view">
      <AIScreenerPanel />
      {/* ... existing screener content ... */}
```

Wrap existing content in the `<div className="screener-view">` if not already wrapped. The exact insertion point is right after the `return (` of the ScreenerView component.

- [ ] **Step 5: Run tsc**

Run: `cd D:/AI/hermesStockAgent/frontend && node node_modules/typescript/bin/tsc --noEmit`
Expected: 0 errors

- [ ] **Step 6: Commit**

```bash
cd D:/AI/hermesStockAgent
git add frontend/src/api/screener.ts frontend/src/components/AIScreenerPanel.tsx frontend/src/components/ScreenerView.tsx frontend/src/index.css
git commit -m "feat: add AIScreenerPanel component with SSE streaming + SkillChip toggle"
```

---

### Task 4: 集成验证

**Files:** All modified files from Tasks 1-3

- [ ] **Step 1: Run backend tests**

Run: `cd D:/AI/hermesStockAgent/backend && D:/AI/hermesStockAgent/backend/.venv/Scripts/python -m pytest tests/test_screener.py tests/test_diagnosis.py -v --tb=short`
Expected: All pass

- [ ] **Step 2: Run tsc**

Run: `cd D:/AI/hermesStockAgent/frontend && node node_modules/typescript/bin/tsc --noEmit`
Expected: 0 errors

- [ ] **Step 3: Push**

```bash
cd D:/AI/hermesStockAgent
git push
```
