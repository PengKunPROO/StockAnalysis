# News Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 新闻面板 + Hermes agent web_search 获取财经新闻 + 内联影响分析。

**Architecture:** 后端 Hermes subprocess 搜索新闻 → SQLite 缓存(当天) → API → 前端 NewsPanel 内联分析。

**Tech Stack:** FastAPI, SQLite, subprocess(hermes), React+TypeScript

## Global Constraints

- 新闻当天缓存，第二天自动失效
- web_search 通过 Hermes agent 的 web_search 工具
- 面板位置：K线图下方，max-height 200px
- 分析内联展开，不跳聊天

---

### Task 1: 后端新闻 API

**Files:**
- Create: `backend/app/db/news_models.py` (或追加到 models.py)
- Create: `backend/app/api/v1/news.py`
- Modify: `backend/app/api/v1/router.py` (注册路由)
- Modify: `backend/app/db/database.py` (建表)

- [ ] **Step 1: 追加 DB 模型**

`backend/app/db/models.py` 末尾追加：

```python
class StockNews(Base):
    __tablename__ = "stock_news"
    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False)
    title = Column(Text, nullable=False)
    source = Column(String(100))
    url = Column(Text)
    summary = Column(Text)
    fetched_at = Column(Date, nullable=False)
    __table_args__ = (UniqueConstraint('stock_code', 'title', 'fetched_at'),)
```

- [ ] **Step 2: 创建新闻 API**

`backend/app/api/v1/news.py`:

```python
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json, subprocess, os, re, asyncio
from datetime import date
from app.db.database import get_session_factory
from app.db.models import StockNews

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/stock/{code}")
async def get_news(code: str):
    today = date.today()
    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(StockNews).where(
                StockNews.stock_code == code,
                StockNews.fetched_at == today,
            ).order_by(StockNews.id.desc())
        )
        cached = result.scalars().all()
        if cached:
            return {"code": code, "news": [
                {"id": n.id, "title": n.title, "source": n.source, "url": n.url, "summary": n.summary}
                for n in cached
            ], "cached": True}

    # Fetch via Hermes agent
    name = code  # Will be resolved by search
    prompt = f'搜索 "{code}" 最近3天的重要财经新闻，返回JSON数组，格式: [{{"title":"...","source":"东方财富/雪球/新浪等","url":"...","summary":"一句话摘要"}}]。只返回JSON，不要其他文字。最多5条。'

    env = {**os.environ, "NO_COLOR": "1"}
    proc = subprocess.Popen(
        ["hermes", "chat", "-q", prompt],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env, text=True, encoding="utf-8", errors="replace",
    )
    
    output = proc.stdout.read()
    proc.wait(timeout=60)

    # Extract JSON from output
    json_match = re.search(r'\[[\s\S]*\]', output)
    if not json_match:
        return {"code": code, "news": [], "cached": False, "error": "No news found"}

    try:
        articles = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return {"code": code, "news": [], "cached": False, "error": "Parse error"}

    # Save to DB
    async with factory() as session:
        for a in articles[:5]:
            session.add(StockNews(
                stock_code=code, title=a.get("title", ""),
                source=a.get("source", ""), url=a.get("url", ""),
                summary=a.get("summary", ""), fetched_at=today,
            ))
        await session.commit()

    return {"code": code, "news": [
        {"title": a.get("title",""), "source": a.get("source",""), "url": a.get("url",""), "summary": a.get("summary","")}
        for a in articles[:5]
    ], "cached": False}


class AnalyzeRequest(BaseModel):
    title: str
    source: str = ""
    summary: str = ""


@router.post("/stock/{code}/analyze")
async def analyze_news(code: str, req: AnalyzeRequest):
    prompt = f'分析这条新闻对股票 {code} 的影响。结合技术面和基本面，判断是利好/利空/中性，短期和中期影响。\n\n新闻: {req.title}\n来源: {req.source}\n摘要: {req.summary}\n\n请用中文简要分析，给出影响评级（强利好/利好/中性/利空/强利空）。'

    async def event_stream():
        env = {**os.environ, "NO_COLOR": "1"}
        proc = subprocess.Popen(
            ["hermes", "chat", "-q", prompt],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, text=True, encoding="utf-8", errors="replace",
        )
        in_analysis = False
        for line in proc.stdout:
            if '╭─' in line: in_analysis = True; continue
            if '╰─' in line: continue
            if not in_analysis: continue
            clean = line.strip()
            if clean:
                yield f"data: {json.dumps({'content': clean + chr(10)}, ensure_ascii=False)}\n\n"
        proc.wait()
        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 3: 注册路由**

`backend/app/api/v1/router.py` 添加：
```python
from . import news
router.include_router(news.router)
```

- [ ] **Step 4: 验证**

```bash
cd backend && .venv/Scripts/python.exe -c "from app.main import app; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: news API — agent web_search + daily cache + inline analysis"
```

---

### Task 2: 前端 NewsPanel 组件

**Files:**
- Create: `frontend/src/components/NewsPanel.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/index.css`

- [ ] **Step 1: 创建 NewsPanel.tsx**

```typescript
import { useState, useEffect, useRef } from 'react'
import { useApp } from '../contexts/AppContext'

interface NewsItem {
  id?: number; title: string; source: string; url?: string; summary?: string
}

export default function NewsPanel() {
  const { state } = useApp()
  const stock = state.currentStock
  const [news, setNews] = useState<NewsItem[]>([])
  const [loading, setLoading] = useState(false)
  const [analyzing, setAnalyzing] = useState<number | null>(null)
  const [analysis, setAnalysis] = useState('')
  const [error, setError] = useState('')
  const readerRef = useRef<AbortController | null>(null)

  useEffect(() => { if (stock) fetchNews() }, [stock])

  const fetchNews = async () => {
    if (!stock) return
    setLoading(true); setError('')
    try {
      const r = await fetch(`/api/v1/news/stock/${stock.code}`)
      const d = await r.json()
      setNews(d.news || [])
      if (d.error) setError(d.error)
    } catch { setError('获取新闻失败') }
    setLoading(false)
  }

  const analyze = async (item: NewsItem, idx: number) => {
    if (analyzing === idx) { setAnalyzing(null); return }
    setAnalyzing(idx); setAnalysis('')
    try {
      const ctrl = new AbortController(); readerRef.current = ctrl
      const r = await fetch(`/api/v1/news/stock/${stock!.code}/analyze`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: item.title, source: item.source, summary: item.summary || '' }),
        signal: ctrl.signal,
      })
      const reader = r.body!.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n'); buf = lines.pop() || ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const d = JSON.parse(line.slice(6))
              if (d.done) return
              if (d.content) setAnalysis(prev => prev + d.content)
            } catch {}
          }
        }
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') setAnalysis('分析失败: ' + e.message)
    }
  }

  if (!stock) return null

  return (
    <div className="news-panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <span style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase' }}>📰 相关新闻</span>
        <button onClick={fetchNews} disabled={loading} style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: 11 }} title="刷新新闻">
          {loading ? '搜索中...' : '刷新'}
        </button>
      </div>
      {error && <div style={{ color: 'var(--down)', fontSize: 11, marginBottom: 4 }}>{error}</div>}
      {news.map((item, i) => (
        <div key={i}>
          <div className="news-item" onClick={() => analyze(item, i)}>
            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.title}</span>
            <span style={{ color: 'var(--muted)', fontSize: 10, whiteSpace: 'nowrap' }}>{item.source}</span>
          </div>
          {analyzing === i && (
            <div className="news-analysis">
              {analysis || <span style={{ color: 'var(--muted)', fontStyle: 'italic' }}>🤖 分析中...</span>}
            </div>
          )}
        </div>
      ))}
      {!loading && news.length === 0 && !error && (
        <div style={{ color: 'var(--muted)', fontSize: 11, textAlign: 'center', padding: 8 }}>暂无新闻</div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: 集成到 App.tsx**

在 `<KlineChart />` 之后添加 `<NewsPanel />`：

```typescript
import NewsPanel from './components/NewsPanel'
// ... 在 KlineChart 后:
<KlineChart />
<NewsPanel />
```

- [ ] **Step 3: 添加 CSS**

`index.css` 追加：

```css
.news-panel {
  background: var(--surface);
  border-top: 1px solid var(--border);
  padding: 6px 12px;
  max-height: 180px;
  overflow-y: auto;
  flex-shrink: 0;
}
.news-item {
  display: flex; align-items: center; gap: 6px;
  padding: 3px 0; border-bottom: 1px solid rgba(26,26,58,0.5);
  font-size: 12px; cursor: pointer;
}
.news-item:hover { color: var(--accent); }
.news-analysis {
  padding: 6px 10px; background: rgba(0,229,255,0.04);
  font-size: 11px; line-height: 1.4;
  border-left: 2px solid var(--accent);
  margin: 2px 0 6px 8px; color: var(--text);
}
```

- [ ] **Step 4: 验证构建**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: NewsPanel — stock news with inline AI analysis"
```

---

### Task 3: 集成验证 + 测试

- [ ] **Step 1: 后端测试**

`backend/tests/test_news.py`:

```python
def test_news_endpoint_returns_200(client, stock_code):
    r = client.get(f"/api/v1/news/stock/{stock_code}")
    assert r.status_code == 200
    assert "news" in r.json()


def test_news_structure(client, stock_code):
    r = client.get(f"/api/v1/news/stock/{stock_code}")
    data = r.json()
    for item in data.get("news", []):
        assert "title" in item
        assert "source" in item
```

- [ ] **Step 2: 运行测试**

```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/test_news.py -v
```

- [ ] **Step 3: 前端构建**

```bash
cd frontend && npx tsc --noEmit && npx vite build --logLevel error
```

- [ ] **Step 4: Commit + Push**

```bash
git add -A && git commit -m "chore: news integration tests" && git push
```
