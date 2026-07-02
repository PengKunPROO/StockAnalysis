# 阶段2：个股分析与AI诊断 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build stock analysis UI with K-line chart, technical indicators, fundamental cards, and a multi-turn AI diagnosis chat system with Function Calling.

**Architecture:** React + lightweight-charts frontend talking to FastAPI backend. Backend adds indicator calculator (pure functions), AI diagnosis engine (tool-calling loop with SSE streaming), skill file manager, and watchlist storage. AI uses function tools to fetch stock data on demand.

**Tech Stack:** React 18 + TypeScript + Vite, lightweight-charts, FastAPI, numpy/pandas for indicators, httpx + sse-starlette for LLM streaming, SQLite for sessions.

## Global Constraints

- Stock codes: `sh.600519`, `us.AAPL` — same as Phase 1
- All amounts and indicators computed server-side, returned as JSON
- AI diagnosis: function-calling loop capped at 5 rounds
- SSE streaming for all AI responses
- Skill files in `backend/skills/`, managed via UI upload
- Frontend talks to backend at `http://localhost:8000` (proxied via Vite)
- `npm run dev` starts frontend, `uvicorn app.main:app` starts backend

---

## File Structure (new/modified)

```
hermesStockAgent/
├── backend/
│   ├── app/
│   │   ├── config.py            # ADD: diagnosis LLM settings
│   │   ├── indicators/          # NEW
│   │   │   ├── __init__.py
│   │   │   ├── macd.py
│   │   │   ├── rsi.py
│   │   │   ├── kdj.py
│   │   │   └── boll.py
│   │   ├── diagnosis/           # NEW
│   │   │   ├── __init__.py
│   │   │   ├── engine.py
│   │   │   ├── tools.py
│   │   │   ├── sessions.py
│   │   │   └── skills_manager.py
│   │   ├── api/v1/
│   │   │   ├── indicators.py    # NEW
│   │   │   ├── diagnosis.py     # NEW
│   │   │   ├── skills_api.py    # NEW
│   │   │   ├── watchlist.py     # NEW
│   │   │   └── router.py        # MODIFY
│   │   └── db/
│   │       └── models.py        # MODIFY: add diagnosis tables
│   ├── skills/                  # NEW
│   │   └── .gitkeep
│   └── requirements.txt         # MODIFY
├── frontend/                    # NEW (all)
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── App.css
│       ├── api/
│       │   ├── client.ts
│       │   ├── stocks.ts
│       │   ├── diagnosis.ts
│       │   ├── skills.ts
│       │   └── watchlist.ts
│       ├── components/
│       │   ├── SearchBar.tsx
│       │   ├── KlineChart.tsx
│       │   ├── InfoCards.tsx
│       │   ├── DiagnosisPanel.tsx
│       │   ├── WatchlistSidebar.tsx
│       │   ├── SkillManager.tsx
│       │   └── ChatMessage.tsx
│       ├── contexts/
│       │   └── AppContext.tsx
│       └── types/
│           └── index.ts
```

---

### Task 1: Backend Foundation — Indicators + Config + DB

Add dependencies, indicator calculator, DB tables, config.

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/config.py`
- Create: `backend/app/indicators/__init__.py`
- Create: `backend/app/indicators/macd.py`
- Create: `backend/app/indicators/rsi.py`
- Create: `backend/app/indicators/kdj.py`
- Create: `backend/app/indicators/boll.py`
- Modify: `backend/app/db/models.py`
- Create: `backend/skills/.gitkeep`

**Interfaces:**
- Consumes: Phase 1 data engine, DB models
- Produces: `compute_all(code, period, start, end)` → dict of indicators; new DB tables

- [ ] **Step 1: Add deps to requirements.txt**

```python
# Append to backend/requirements.txt:
numpy==2.2.3
sse-starlette==2.2.1
python-multipart==0.0.20
```

- [ ] **Step 2: Install new deps**

```bash
cd backend && uv pip install numpy sse-starlette python-multipart
```

- [ ] **Step 3: Add LLM config to config.py**

```python
# Add to Settings class:
diagnosis_llm_provider: str = "deepseek"
diagnosis_llm_model: str = "deepseek-v4-pro"
diagnosis_llm_api_key: str = ""
diagnosis_llm_base_url: str = "https://api.deepseek.com/v1"
diagnosis_max_tool_rounds: int = 5
```

- [ ] **Step 4: Create indicators/__init__.py**

```python
"""Technical indicator calculation engine."""
from .macd import compute_macd
from .rsi import compute_rsi
from .kdj import compute_kdj
from .boll import compute_boll


async def compute_all(klines: list[dict]) -> list[dict]:
    """Compute all indicators for a list of kline bars."""
    if not klines:
        return []
    macd = compute_macd(klines)
    rsi = compute_rsi(klines)
    kdj = compute_kdj(klines)
    boll = compute_boll(klines)
    result = []
    for i, k in enumerate(klines):
        result.append({
            "date": k["date"],
            "macd": macd[i] if i < len(macd) else None,
            "rsi": rsi[i] if i < len(rsi) else None,
            "kdj": kdj[i] if i < len(kdj) else None,
            "boll": boll[i] if i < len(boll) else None,
        })
    return result
```

- [ ] **Step 5: Create indicators/macd.py**

```python
def compute_macd(klines: list[dict], fast=12, slow=26, signal=9) -> list[dict]:
    closes = [k["close"] for k in klines]

    def _ema(data, period):
        result = []
        multiplier = 2 / (period + 1)
        for i, val in enumerate(data):
            if i == 0:
                result.append(val)
            else:
                result.append((val - result[-1]) * multiplier + result[-1])
        return result

    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    dif = [f - s for f, s in zip(ema_fast, ema_slow)]
    dea = _ema(dif, signal)
    macd = [(d - e) * 2 for d, e in zip(dif, dea)]
    return [
        {"dif": round(dif[i], 4), "dea": round(dea[i], 4), "macd": round(macd[i], 4)}
        for i in range(len(klines))
    ]
```

- [ ] **Step 6: Create indicators/rsi.py**

```python
def compute_rsi(klines: list[dict], period=14) -> list[dict]:
    closes = [k["close"] for k in klines]
    result = []
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    for i in range(len(closes)):
        if i < period:
            result.append({"rsi14": None})
        else:
            avg_gain = sum(gains[i - period:i]) / period
            avg_loss = sum(losses[i - period:i]) / period
            if avg_loss == 0:
                result.append({"rsi14": 100.0})
            else:
                rs = avg_gain / avg_loss
                result.append({"rsi14": round(100 - 100 / (1 + rs), 2)})
    return result
```

- [ ] **Step 7: Create indicators/kdj.py**

```python
def compute_kdj(klines: list[dict], n=9, m1=3, m2=3) -> list[dict]:
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]
    closes = [k["close"] for k in klines]
    result = []
    k_vals = [50.0] * len(klines)
    d_vals = [50.0] * len(klines)
    for i in range(n - 1, len(klines)):
        hn = max(highs[i - n + 1:i + 1])
        ln = min(lows[i - n + 1:i + 1])
        rsv = (closes[i] - ln) / (hn - ln) * 100 if hn != ln else 50
        k_vals[i] = rsv * (1 / m1) + k_vals[i - 1] * (1 - 1 / m1)
        d_vals[i] = k_vals[i] * (1 / m2) + d_vals[i - 1] * (1 - 1 / m2)
    for i in range(len(klines)):
        k = round(k_vals[i], 2)
        d = round(d_vals[i], 2)
        j = round(3 * k - 2 * d, 2)
        result.append({"k": k if i >= n - 1 else None, "d": d if i >= n - 1 else None, "j": j if i >= n - 1 else None})
    return result
```

- [ ] **Step 8: Create indicators/boll.py**

```python
def compute_boll(klines: list[dict], period=20, std_mult=2) -> list[dict]:
    closes = [k["close"] for k in klines]
    result = []
    for i in range(len(closes)):
        if i < period - 1:
            result.append({"upper": None, "mid": None, "lower": None})
        else:
            window = closes[i - period + 1:i + 1]
            mid = sum(window) / period
            variance = sum((x - mid) ** 2 for x in window) / period
            std = variance ** 0.5
            result.append({
                "upper": round(mid + std_mult * std, 4),
                "mid": round(mid, 4),
                "lower": round(mid - std_mult * std, 4),
            })
    return result
```

- [ ] **Step 9: Add DB tables to models.py**

```python
# Add to backend/app/db/models.py:
from sqlalchemy import ForeignKey

class DiagnosisSession(Base):
    __tablename__ = "diagnosis_sessions"
    id = Column(String(36), primary_key=True)
    skill_name = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class SessionStock(Base):
    __tablename__ = "session_stocks"
    session_id = Column(String(36), ForeignKey("diagnosis_sessions.id"), primary_key=True)
    stock_code = Column(String(20), primary_key=True)
    stock_name = Column(String(100), nullable=False)


class DiagnosisMessage(Base):
    __tablename__ = "diagnosis_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("diagnosis_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text)
    tool_calls = Column(Text)
    tool_call_id = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())
```

- [ ] **Step 10: Create skills directory**

```bash
mkdir -p backend/skills && touch backend/skills/.gitkeep
```

- [ ] **Step 11: Verify — import and test indicators**

```bash
cd backend && .venv/Scripts/python -c "
from app.indicators import compute_all
klines = [{'date': f'2026-06-{i:02d}', 'open': 100+i, 'high': 102+i, 'low': 99+i, 'close': 101+i, 'volume': 1000, 'amount': 101000} for i in range(1, 31)]
import asyncio
result = asyncio.run(compute_all(klines))
print(f'Bars: {len(result)}, Last MACD: {result[-1][\"macd\"]}, Last RSI: {result[-1][\"rsi\"]}')
"
```

Expected: `Bars: 30, Last MACD: {'dif': ..., 'dea': ..., 'macd': ...}, Last RSI: {'rsi14': ...}`

- [ ] **Step 12: Commit**

```bash
git add -A && git commit -m "feat: indicators engine, diagnosis DB tables, config"
```

---

### Task 2: Indicators API + Skill Manager Backend

**Files:**
- Create: `backend/app/api/v1/indicators.py`
- Create: `backend/app/diagnosis/__init__.py`
- Create: `backend/app/diagnosis/skills_manager.py`
- Create: `backend/app/api/v1/skills_api.py`
- Create: `backend/app/api/v1/watchlist.py`
- Modify: `backend/app/api/v1/router.py`

**Interfaces:**
- Consumes: `app.engine.data_engine.engine`, `app.indicators.compute_all`
- Produces: `/api/v1/stock/{code}/indicators`, `/api/v1/skills/*`, `/api/v1/watchlist/*`

- [ ] **Step 1: Create indicators API**

`backend/app/api/v1/indicators.py`:

```python
from fastapi import APIRouter, Query
from app.engine.data_engine import engine
from app.indicators import compute_all

router = APIRouter(tags=["indicators"])


@router.get("/stock/{code}/indicators")
async def get_indicators(
    code: str,
    period: str = Query("daily", pattern=r"^(daily|weekly|monthly)$"),
    days: int = Query(60, ge=20, le=500),
):
    from datetime import date, timedelta
    end = str(date.today())
    start = str(date.today() - timedelta(days=days * 2))
    klines, _ = await engine.get_klines(code, period, start, end)
    indicators = await compute_all(klines[-days:]) if klines else []
    return {"code": code, "period": period, "data": indicators}
```

- [ ] **Step 2: Create skills_manager.py**

`backend/app/diagnosis/__init__.py`:
```python
# AI Diagnosis Engine
```

`backend/app/diagnosis/skills_manager.py`:
```python
"""Skill file management."""
import os
import re
import yaml
from pathlib import Path

SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"


def _parse_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter from markdown content."""
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}


def list_skills() -> list[dict]:
    """Return all installed skills with metadata."""
    skills = []
    if not SKILLS_DIR.exists():
        return skills
    for f in sorted(SKILLS_DIR.glob("*.md")):
        content = f.read_text(encoding="utf-8")
        meta = _parse_frontmatter(content)
        skills.append({
            "name": meta.get("name", f.stem),
            "description": meta.get("description", ""),
            "mode": meta.get("mode", "general"),
            "filename": f.name,
        })
    return skills


def get_skill_content(name: str) -> str | None:
    """Get full skill markdown content by name."""
    for f in SKILLS_DIR.glob("*.md"):
        content = f.read_text(encoding="utf-8")
        meta = _parse_frontmatter(content)
        if meta.get("name") == name or f.stem == name:
            return content
    return None


def save_skill(filename: str, content: bytes) -> dict:
    """Save uploaded skill file. Returns metadata."""
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    path = SKILLS_DIR / filename
    path.write_bytes(content)
    text = path.read_text(encoding="utf-8")
    meta = _parse_frontmatter(text)
    return {
        "name": meta.get("name", path.stem),
        "description": meta.get("description", ""),
        "mode": meta.get("mode", "general"),
        "filename": filename,
    }


def delete_skill(name: str) -> bool:
    """Delete a skill file by name. Returns True if deleted."""
    for f in SKILLS_DIR.glob("*.md"):
        content = f.read_text(encoding="utf-8")
        meta = _parse_frontmatter(content)
        if meta.get("name") == name or f.stem == name:
            f.unlink()
            return True
    return False
```

- [ ] **Step 3: Create skills API**

`backend/app/api/v1/skills_api.py`:
```python
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.diagnosis.skills_manager import list_skills, get_skill_content, save_skill, delete_skill

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("")
async def api_list_skills():
    return {"skills": list_skills()}


@router.get("/{name}")
async def api_get_skill(name: str):
    content = get_skill_content(name)
    if content is None:
        raise HTTPException(404, f"Skill '{name}' not found")
    return {"name": name, "content": content}


@router.post("/upload")
async def api_upload_skill(file: UploadFile = File(...)):
    if not file.filename.endswith(".md"):
        raise HTTPException(400, "Only .md files allowed")
    content = await file.read()
    result = save_skill(file.filename, content)
    return result


@router.delete("/{name}")
async def api_delete_skill(name: str):
    if not delete_skill(name):
        raise HTTPException(404, f"Skill '{name}' not found")
    return {"deleted": name}
```

- [ ] **Step 4: Create watchlist API**

`backend/app/api/v1/watchlist.py`:
```python
"""Simple watchlist stored in SQLite."""
from fastapi import APIRouter
from pydantic import BaseModel
from app.db.database import get_session_factory
from app.db.models import Stock

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistItem(BaseModel):
    code: str
    name: str


@router.get("")
async def get_watchlist():
    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select
        result = await session.execute(select(Stock))
        stocks = result.scalars().all()
        return {"stocks": [{"code": s.code, "name": s.name, "market": s.market} for s in stocks]}


@router.post("")
async def add_to_watchlist(item: WatchlistItem):
    from app.db import queries
    factory = get_session_factory()
    async with factory() as session:
        market = "us" if item.code.startswith("us.") else "a_share"
        await queries.upsert_stock(session, item.code, item.name, market, "")
        await session.commit()
    return {"added": item.code}
```

- [ ] **Step 5: Update router.py**

```python
from fastapi import APIRouter
from . import stocks, financial, search, index, health, indicators, skills_api, watchlist

router = APIRouter(prefix="/api/v1")
router.include_router(stocks.router)
router.include_router(financial.router)
router.include_router(search.router)
router.include_router(index.router)
router.include_router(health.router)
router.include_router(indicators.router)
router.include_router(skills_api.router)
router.include_router(watchlist.router)
```

- [ ] **Step 6: Test indicators endpoint**

```bash
cd backend && .venv/Scripts/python -m uvicorn app.main:app --port 8000 &
sleep 3
curl "http://localhost:8000/api/v1/stock/sh.600519/indicators?days=30"
```

Expected: JSON with `code`, `data` array containing `{date, macd, rsi, kdj, boll}`

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: indicators API, skill manager, watchlist API"
```

---

### Task 3: AI Diagnosis Engine (Function Calling + SSE)

**Files:**
- Create: `backend/app/diagnosis/tools.py`
- Create: `backend/app/diagnosis/sessions.py`
- Create: `backend/app/diagnosis/engine.py`

**Interfaces:**
- Consumes: `app.indicators.compute_all`, `app.engine.data_engine.engine`
- Produces: `DiagnosisEngine.run_chat()` → SSE stream

- [ ] **Step 1: Create tools.py**

```python
"""Tool definitions and handlers for AI diagnosis."""
import json
from app.engine.data_engine import engine
from app.indicators import compute_all

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_kline",
            "description": "获取股票K线数据，返回OHLCV数组。用于分析趋势、形态、支撑阻力位。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "股票代码，如 sh.600519"},
                    "period": {"type": "string", "enum": ["daily", "weekly", "monthly"]},
                    "limit": {"type": "integer", "description": "最近多少条数据，默认60"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_indicators",
            "description": "获取技术指标：MACD、RSI(14)、KDJ、BOLL(20)。用于分析买卖信号、超买超卖。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "股票代码"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_financials",
            "description": "获取财务数据：营收、净利润、ROE、PE、PB、资产负债率。用于基本面分析。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "股票代码"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_realtime",
            "description": "获取最新行情：当前价格、涨跌幅。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "股票代码"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_stocks",
            "description": "搜索股票。当用户提及的股票不在已知列表时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "股票名称或代码"}
                },
                "required": ["keyword"]
            }
        }
    },
]


async def execute_tool(name: str, args: dict) -> str:
    """Execute a tool and return JSON string result."""
    from datetime import date, timedelta

    if name == "get_kline":
        code = args["code"]
        period = args.get("period", "daily")
        limit = args.get("limit", 60)
        end = str(date.today())
        start = str(date.today() - timedelta(days=limit * 3))
        data, _ = await engine.get_klines(code, period, start, end)
        return json.dumps(data[-limit:], ensure_ascii=False)

    elif name == "get_indicators":
        code = args["code"]
        end = str(date.today())
        start = str(date.today() - timedelta(days=180))
        klines, _ = await engine.get_klines(code, "daily", start, end)
        if not klines:
            return json.dumps({"error": "No data"}, ensure_ascii=False)
        indicators = await compute_all(klines[-60:])
        return json.dumps(indicators[-10:], ensure_ascii=False)

    elif name == "get_financials":
        code = args["code"]
        data, _ = await engine.get_financial(code)
        return json.dumps(data, ensure_ascii=False)

    elif name == "get_realtime":
        code = args["code"]
        data, _ = await engine.get_realtime(code)
        return json.dumps(data, ensure_ascii=False)

    elif name == "search_stocks":
        keyword = args["keyword"]
        results, _ = await engine.search(keyword)
        return json.dumps(results[:5], ensure_ascii=False)

    return json.dumps({"error": f"Unknown tool: {name}"})
```

- [ ] **Step 2: Create sessions.py**

```python
"""Session storage for AI diagnosis conversations."""
import uuid
from datetime import datetime
from app.db.database import get_session_factory
from app.db.models import DiagnosisSession, SessionStock, DiagnosisMessage


async def create_session(skill_name: str, model: str, stock_codes: list[dict]) -> str:
    sid = str(uuid.uuid4())
    factory = get_session_factory()
    async with factory() as session:
        session.add(DiagnosisSession(id=sid, skill_name=skill_name, model=model))
        for s in stock_codes:
            session.add(SessionStock(session_id=sid, stock_code=s["code"], stock_name=s["name"]))
        await session.commit()
    return sid


async def add_stock_to_session(session_id: str, code: str, name: str):
    factory = get_session_factory()
    async with factory() as session:
        session.add(SessionStock(session_id=session_id, stock_code=code, stock_name=name))
        await session.commit()


async def get_session_stocks(session_id: str) -> list[dict]:
    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(SessionStock).where(SessionStock.session_id == session_id)
        )
        return [{"code": s.stock_code, "name": s.stock_name} for s in result.scalars().all()]


async def get_messages(session_id: str) -> list[dict]:
    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(DiagnosisMessage)
            .where(DiagnosisMessage.session_id == session_id)
            .order_by(DiagnosisMessage.id.asc())
        )
        return [
            {
                "role": m.role,
                "content": m.content,
                "tool_calls": m.tool_calls,
                "tool_call_id": m.tool_call_id,
                "created_at": str(m.created_at),
            }
            for m in result.scalars().all()
        ]


async def save_message(session_id: str, role: str, content: str = None,
                       tool_calls: str = None, tool_call_id: str = None):
    factory = get_session_factory()
    async with factory() as session:
        msg = DiagnosisMessage(
            session_id=session_id, role=role,
            content=content, tool_calls=tool_calls, tool_call_id=tool_call_id,
        )
        session.add(msg)
        # Update session timestamp
        from sqlalchemy import update
        await session.execute(
            update(DiagnosisSession).where(DiagnosisSession.id == session_id)
            .values(updated_at=datetime.now())
        )
        await session.commit()


async def list_sessions() -> list[dict]:
    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(DiagnosisSession).order_by(DiagnosisSession.updated_at.desc()).limit(50)
        )
        return [
            {"id": s.id, "skill_name": s.skill_name, "model": s.model,
             "created_at": str(s.created_at), "updated_at": str(s.updated_at)}
            for s in result.scalars().all()
        ]
```

- [ ] **Step 3: Create engine.py**

```python
"""AI Diagnosis Engine — Function Calling + SSE streaming."""
import json
import httpx
import logging
from typing import AsyncGenerator
from app.config import settings
from app.diagnosis.tools import TOOL_DEFINITIONS, execute_tool
from app.diagnosis.skills_manager import get_skill_content
from app.diagnosis.sessions import (
    get_session_stocks, get_messages, save_message,
)

logger = logging.getLogger(__name__)


async def run_chat(session_id: str, user_message: str) -> AsyncGenerator[str, None]:
    """Main chat loop with function calling. Yields SSE chunks."""
    # Load session context
    stocks = await get_session_stocks(session_id)
    messages = await get_messages(session_id)

    # Get session metadata
    from app.diagnosis.sessions import get_session_factory as _gsf
    factory = _gsf()
    async with factory() as sess:
        from sqlalchemy import select
        from app.db.models import DiagnosisSession
        result = await sess.execute(select(DiagnosisSession).where(DiagnosisSession.id == session_id))
        ds = result.scalar_one()

    skill_content = get_skill_content(ds.skill_name) or ""
    stock_list = ", ".join(f"{s['name']}({s['code']})" for s in stocks)

    system_prompt = f"""{skill_content}

当前可分析的股票: {stock_list}

你可以使用提供的工具函数查询股票数据。需要数据时请主动调用工具，不要猜测。
分析时引用具体数值，给出有理有据的判断。"""

    # Build message array
    llm_messages = [{"role": "system", "content": system_prompt}]

    # Add history (last 20 messages to stay within context)
    for m in messages[-20:]:
        msg = {"role": m["role"]}
        if m["content"]:
            msg["content"] = m["content"]
        if m["tool_calls"]:
            msg["tool_calls"] = json.loads(m["tool_calls"])
        if m["tool_call_id"]:
            msg["tool_call_id"] = m["tool_call_id"]
        llm_messages.append(msg)

    # Add new user message
    llm_messages.append({"role": "user", "content": user_message})
    await save_message(session_id, "user", content=user_message)

    # Function calling loop (max rounds)
    max_rounds = settings.diagnosis_max_tool_rounds
    for round_num in range(max_rounds + 1):
        if round_num >= max_rounds:
            yield f"data: {json.dumps({'error': '达到最大工具调用轮次，请简化问题'})}\n\n"
            return

        response = await _call_llm(llm_messages, ds.model)

        if response.get("tool_calls"):
            # Save assistant message with tool calls
            tc_json = json.dumps(response["tool_calls"], ensure_ascii=False)
            await save_message(session_id, "assistant", tool_calls=tc_json)

            # Execute tools
            for tc in response["tool_calls"]:
                func_name = tc["function"]["name"]
                func_args = json.loads(tc["function"]["arguments"])
                result = await execute_tool(func_name, func_args)
                await save_message(session_id, "tool", content=result, tool_call_id=tc["id"])
                llm_messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

            llm_messages.append({"role": "assistant", "tool_calls": response["tool_calls"]})
        else:
            # Text response — stream it
            content = response.get("content", "")
            await save_message(session_id, "assistant", content=content)
            yield f"data: {json.dumps({'content': content, 'done': True}, ensure_ascii=False)}\n\n"
            return


async def _call_llm(messages: list[dict], model: str) -> dict:
    """Call LLM API with tools."""
    api_key = settings.diagnosis_llm_api_key or __import__('os').environ.get("DEEPSEEK_API_KEY", "")
    base_url = settings.diagnosis_llm_base_url

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "tools": TOOL_DEFINITIONS,
                "temperature": 0.3,
                "max_tokens": 2000,
            },
        )
        resp.raise_for_status()
        choice = resp.json()["choices"][0]
        message = choice["message"]
        return {
            "content": message.get("content", ""),
            "tool_calls": message.get("tool_calls"),
        }
```

- [ ] **Step 4: Create diagnosis API endpoint**

`backend/app/api/v1/diagnosis.py`:
```python
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.diagnosis.engine import run_chat
from app.diagnosis.sessions import (
    create_session, add_stock_to_session, get_session_stocks,
    get_messages, list_sessions,
)

router = APIRouter(prefix="/diagnosis", tags=["diagnosis"])


class ChatRequest(BaseModel):
    session_id: str | None = None
    skill: str = "默认分析"
    model: str = "deepseek-v4-pro"
    message: str
    stock_codes: list[dict] | None = None  # [{"code":"sh.600519","name":"茅台"}]


@router.post("/chat")
async def chat(req: ChatRequest):
    sid = req.session_id
    if not sid:
        sid = await create_session(req.skill, req.model, req.stock_codes or [])
    elif req.stock_codes:
        for s in req.stock_codes:
            await add_stock_to_session(sid, s["code"], s["name"])

    async def event_stream():
        yield f"data: {{\"session_id\": \"{sid}\"}}\n\n"
        async for chunk in run_chat(sid, req.message):
            yield chunk

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/sessions")
async def api_list_sessions():
    return {"sessions": await list_sessions()}


@router.get("/sessions/{session_id}")
async def api_get_session(session_id: str):
    stocks = await get_session_stocks(session_id)
    messages = await get_messages(session_id)
    return {"session_id": session_id, "stocks": stocks, "messages": messages}
```

- [ ] **Step 5: Register diagnosis routes in router.py**

Add to router.py:
```python
from . import diagnosis
# inside, add:
router.include_router(diagnosis.router)
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: AI diagnosis engine with function calling and SSE"
```

---

### Task 4: Frontend Scaffolding (Vite + React + deps)

- [ ] **Step 1: Initialize Vite project**

```bash
cd /d/AI/hermesStockAgent
npm create vite@latest frontend -- --template react-ts 2>&1
cd frontend
npm install lightweight-charts 2>&1
```

- [ ] **Step 2: Configure Vite proxy**

`frontend/vite.config.ts`:
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
```

- [ ] **Step 3: Create types**

`frontend/src/types/index.ts`:
```typescript
export interface StockInfo {
  code: string
  name: string
  market: string
  industry: string
}

export interface KlineBar {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount: number
}

export interface IndicatorPoint {
  date: string
  macd: { dif: number; dea: number; macd: number } | null
  rsi: { rsi14: number } | null
  kdj: { k: number; d: number; j: number } | null
  boll: { upper: number; mid: number; lower: number } | null
}

export interface SkillMeta {
  name: string
  description: string
  mode: string
  filename: string
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at?: string
}

export interface DiagnosisSession {
  id: string
  skill_name: string
  model: string
  created_at: string
  stocks: { code: string; name: string }[]
}

export interface WatchlistItem {
  code: string
  name: string
  market: string
  price?: number
  changePct?: number
}
```

- [ ] **Step 4: Create API client**

`frontend/src/api/client.ts`:
```typescript
const BASE = '/api/v1'

export async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status}`)
  return res.json()
}

export async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status}`)
  return res.json()
}

export async function del(path: string): Promise<void> {
  await fetch(`${BASE}${path}`, { method: 'DELETE' })
}
```

- [ ] **Step 5: Create API modules**

`frontend/src/api/stocks.ts`:
```typescript
import { get } from './client'
import type { StockInfo, KlineBar, IndicatorPoint } from '../types'

export const searchStocks = (q: string) =>
  get<{ results: StockInfo[]; count: number }>(`/search?q=${encodeURIComponent(q)}`)

export const getKline = (code: string, period = 'daily', start = '2024-01-01', end = '2026-12-31') =>
  get<{ code: string; data: KlineBar[] }>(`/stock/${code}/kline?period=${period}&start=${start}&end=${end}`)

export const getIndicators = (code: string, days = 60) =>
  get<{ code: string; data: IndicatorPoint[] }>(`/stock/${code}/indicators?days=${days}`)

export const getFinancial = (code: string) =>
  get<{ code: string; reports: any[] }>(`/stock/${code}/financial`)

export const getRealtime = (code: string) =>
  get<any>(`/stock/${code}/realtime`)
```

`frontend/src/api/skills.ts`:
```typescript
import { get, post, del } from './client'
import type { SkillMeta } from '../types'

export const listSkills = () => get<{ skills: SkillMeta[] }>('/skills')
export const getSkillContent = (name: string) => get<{ name: string; content: string }>(`/skills/${name}`)
export const uploadSkill = async (file: File) => {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch('/api/v1/skills/upload', { method: 'POST', body: form })
  return res.json()
}
export const deleteSkill = (name: string) => del(`/skills/${name}`)
```

`frontend/src/api/watchlist.ts`:
```typescript
import { get, post, del } from './client'
import type { WatchlistItem } from '../types'

export const getWatchlist = () => get<{ stocks: WatchlistItem[] }>('/watchlist')
export const addToWatchlist = (code: string, name: string) =>
  post('/watchlist', { code, name })
export const removeFromWatchlist = (code: string) => del(`/watchlist/${code}`)
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: frontend scaffolding — Vite, React, API client, types"
```

---

### Task 5: Frontend — App Shell + Context + SearchBar + Stock Detail

**Files:**
- Create: `frontend/src/contexts/AppContext.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.css`
- Create: `frontend/src/components/SearchBar.tsx`

- [ ] **Step 1: Create AppContext**

`frontend/src/contexts/AppContext.tsx`:
```typescript
import React, { createContext, useContext, useReducer } from 'react'
import type { StockInfo, SkillMeta, DiagnosisSession, WatchlistItem } from '../types'

interface AppState {
  currentStock: StockInfo | null
  skills: SkillMeta[]
  sessions: DiagnosisSession[]
  watchlist: WatchlistItem[]
}

const initialState: AppState = {
  currentStock: null,
  skills: [],
  sessions: [],
  watchlist: [],
}

type Action =
  | { type: 'SET_STOCK'; stock: StockInfo }
  | { type: 'SET_SKILLS'; skills: SkillMeta[] }
  | { type: 'SET_SESSIONS'; sessions: DiagnosisSession[] }
  | { type: 'SET_WATCHLIST'; watchlist: WatchlistItem[] }

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case 'SET_STOCK': return { ...state, currentStock: action.stock }
    case 'SET_SKILLS': return { ...state, skills: action.skills }
    case 'SET_SESSIONS': return { ...state, sessions: action.sessions }
    case 'SET_WATCHLIST': return { ...state, watchlist: action.watchlist }
    default: return state
  }
}

const AppCtx = createContext<{ state: AppState; dispatch: React.Dispatch<Action> } | null>(null)

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState)
  return <AppCtx.Provider value={{ state, dispatch }}>{children}</AppCtx.Provider>
}

export function useApp() {
  const ctx = useContext(AppCtx)
  if (!ctx) throw new Error('useApp must be inside AppProvider')
  return ctx
}
```

- [ ] **Step 2: Create SearchBar**

`frontend/src/components/SearchBar.tsx`:
```typescript
import { useState, useRef, useEffect } from 'react'
import { searchStocks } from '../api/stocks'
import { useApp } from '../contexts/AppContext'
import type { StockInfo } from '../types'

export default function SearchBar() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<StockInfo[]>([])
  const [open, setOpen] = useState(false)
  const { dispatch } = useApp()
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleInput = async (val: string) => {
    setQuery(val)
    if (val.length >= 1) {
      const data = await searchStocks(val)
      setResults(data.results)
      setOpen(true)
    } else {
      setOpen(false)
    }
  }

  const select = (s: StockInfo) => {
    dispatch({ type: 'SET_STOCK', stock: s })
    setQuery(s.name)
    setOpen(false)
  }

  return (
    <div ref={ref} style={{ position: 'relative', margin: '8px 0' }}>
      <input
        value={query}
        onChange={e => handleInput(e.target.value)}
        placeholder="输入股票代码或名称..."
        style={{ width: '100%', padding: 10, fontSize: 16, borderRadius: 8, border: '1px solid #444', background: '#222', color: '#eee' }}
      />
      {open && results.length > 0 && (
        <div style={{ position: 'absolute', top: 44, left: 0, right: 0, background: '#333', borderRadius: 8, zIndex: 100, maxHeight: 300, overflowY: 'auto' }}>
          {results.map(s => (
            <div
              key={s.code}
              onClick={() => select(s)}
              style={{ padding: '8px 12px', cursor: 'pointer', borderBottom: '1px solid #444' }}
              onMouseEnter={e => (e.currentTarget.style.background = '#555')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            >
              <span style={{ fontWeight: 600 }}>{s.name}</span>
              <span style={{ color: '#999', marginLeft: 8 }}>{s.code}</span>
              <span style={{ color: '#888', marginLeft: 8 }}>{s.market === 'a_share' ? 'A股' : '美股'}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Create App.tsx with layout**

`frontend/src/App.tsx`:
```typescript
import { useEffect } from 'react'
import { AppProvider, useApp } from './contexts/AppContext'
import { listSkills } from './api/skills'
import { getWatchlist } from './api/watchlist'
import SearchBar from './components/SearchBar'
import KlineChart from './components/KlineChart'
import InfoCards from './components/InfoCards'
import DiagnosisPanel from './components/DiagnosisPanel'
import './App.css'

function StockDetail() {
  const { state } = useApp()
  if (!state.currentStock) return <div className="placeholder">搜索股票开始分析</div>
  return (
    <div className="detail">
      <div className="chart-section">
        <KlineChart />
        <InfoCards />
      </div>
      <div className="diagnosis-section">
        <DiagnosisPanel />
      </div>
    </div>
  )
}

function AppShell() {
  const { dispatch } = useApp()
  useEffect(() => {
    listSkills().then(d => dispatch({ type: 'SET_SKILLS', skills: d.skills }))
    getWatchlist().then(d => dispatch({ type: 'SET_WATCHLIST', watchlist: d.stocks }))
  }, [])

  return (
    <div className="app">
      <SearchBar />
      <StockDetail />
    </div>
  )
}

export default function App() {
  return (
    <AppProvider>
      <AppShell />
    </AppProvider>
  )
}
```

- [ ] **Step 4: Create App.css**

`frontend/src/App.css`:
```css
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #1a1a2e; color: #e0e0e0; font-family: -apple-system, sans-serif; }
.app { max-width: 1400px; margin: 0 auto; padding: 12px; }
.placeholder { display: flex; justify-content: center; align-items: center; height: 300px; color: #666; font-size: 18px; }
.detail { display: flex; gap: 12px; margin-top: 8px; }
.chart-section { flex: 1; min-width: 0; }
.diagnosis-section { width: 420px; flex-shrink: 0; }
```

- [ ] **Step 5: Create placeholder components**

`frontend/src/components/KlineChart.tsx`:
```typescript
export default function KlineChart() {
  return <div style={{ background: '#222', borderRadius: 8, padding: 20, height: 400 }}>K线图加载中...</div>
}
```

`frontend/src/components/InfoCards.tsx`:
```typescript
export default function InfoCards() {
  return <div style={{ background: '#222', borderRadius: 8, padding: 20, marginTop: 8 }}>指标面板</div>
}
```

`frontend/src/components/DiagnosisPanel.tsx`:
```typescript
export default function DiagnosisPanel() {
  return <div style={{ background: '#222', borderRadius: 8, padding: 20, height: '100%' }}>AI诊断面板</div>
}
```

- [ ] **Step 6: Verify — npm run dev**

```bash
cd frontend && npm run dev
# Open http://localhost:5173 — see layout with search bar
```

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: frontend app shell, search bar, layout"
```

---

### Task 6: Frontend — KlineChart + InfoCards

- [ ] **Step 1: Create real KlineChart**

`frontend/src/components/KlineChart.tsx` (replace placeholder):

```typescript
import { useEffect, useRef } from 'react'
import { createChart, ColorType, CrosshairMode } from 'lightweight-charts'
import { useApp } from '../contexts/AppContext'
import { getKline, getIndicators } from '../api/stocks'
import type { KlineBar, IndicatorPoint } from '../types'

export default function KlineChart() {
  const { state } = useApp()
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<any>(null)
  const candleSeriesRef = useRef<any>(null)
  const volumeSeriesRef = useRef<any>(null)

  useEffect(() => {
    if (!state.currentStock || !containerRef.current) return

    const chart = createChart(containerRef.current, {
      layout: { background: { type: ColorType.Solid, color: '#1a1a2e' }, textColor: '#d1d4dc' },
      grid: { vertLines: { color: '#2a2a3e' }, horzLines: { color: '#2a2a3e' } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: '#2a2a3e' },
      timeScale: { borderColor: '#2a2a3e', timeVisible: true },
    })
    chartRef.current = chart

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#26a69a', downColor: '#ef5350', borderUpColor: '#26a69a', borderDownColor: '#ef5350',
      wickUpColor: '#26a69a', wickDownColor: '#ef5350',
    })
    candleSeriesRef.current = candleSeries

    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    })
    volumeSeriesRef.current = volumeSeries
    chart.priceScale('').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } })

    return () => chart.remove()
  }, [state.currentStock])

  useEffect(() => {
    if (!state.currentStock || !candleSeriesRef.current) return
    const code = state.currentStock.code

    getKline(code, 'daily', '2025-01-01', '2026-12-31').then(({ data }) => {
      const candles = data.map((d: KlineBar) => ({
        time: d.date,
        open: d.open, high: d.high, low: d.low, close: d.close,
      }))
      const volumes = data.map((d: KlineBar) => ({
        time: d.date,
        value: d.volume,
        color: d.close >= d.open ? 'rgba(38,166,154,0.3)' : 'rgba(239,83,80,0.3)',
      }))
      candleSeriesRef.current.setData(candles)
      volumeSeriesRef.current.setData(volumes)
      chartRef.current?.timeScale().fitContent()
    })
  }, [state.currentStock])

  return (
    <div style={{ background: '#1a1a2e', borderRadius: 8, overflow: 'hidden' }}>
      <div ref={containerRef} style={{ width: '100%', height: 420 }} />
    </div>
  )
}
```

- [ ] **Step 2: Create real InfoCards**

`frontend/src/components/InfoCards.tsx` (replace placeholder):

```typescript
import { useState, useEffect } from 'react'
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

  const card = { background: '#222', borderRadius: 8, padding: 12, marginBottom: 8 }

  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ display: 'flex', gap: 8 }}>
        <div style={{ ...card, flex: 1 }}>
          <div style={{ color: '#888', fontSize: 12 }}>最新价</div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>
            {realtime?.price?.toFixed(2) || '--'}
          </div>
          <div style={{ color: (realtime?.change_pct || 0) >= 0 ? '#26a69a' : '#ef5350' }}>
            {realtime?.change_pct != null ? `${realtime.change_pct > 0 ? '+' : ''}${realtime.change_pct.toFixed(2)}%` : '--'}
          </div>
        </div>
        <div style={{ ...card, flex: 1 }}>
          <div style={{ color: '#888', fontSize: 12 }}>PE / PB</div>
          <div style={{ fontSize: 16 }}>
            {financial?.pe_ratio?.toFixed(1) || '--'} / {financial?.pb_ratio?.toFixed(1) || '--'}
          </div>
        </div>
        <div style={{ ...card, flex: 1 }}>
          <div style={{ color: '#888', fontSize: 12 }}>ROE</div>
          <div style={{ fontSize: 16 }}>{financial?.roe?.toFixed(1) || '--'}%</div>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <div style={{ ...card, flex: 1 }}>
          <div style={{ color: '#888', fontSize: 12 }}>MACD</div>
          <div style={{ fontSize: 14 }}>
            {indicators?.macd ? (
              <span style={{ color: indicators.macd.macd > 0 ? '#26a69a' : '#ef5350' }}>
                {indicators.macd.macd > 0 ? '金叉' : '死叉'} {indicators.macd.macd.toFixed(2)}
              </span>
            ) : '--'}
          </div>
        </div>
        <div style={{ ...card, flex: 1 }}>
          <div style={{ color: '#888', fontSize: 12 }}>RSI(14)</div>
          <div style={{ fontSize: 14 }}>
            {indicators?.rsi?.rsi14 != null ? (
              <span style={{ color: indicators.rsi.rsi14 > 70 ? '#ef5350' : indicators.rsi.rsi14 < 30 ? '#26a69a' : '#ddd' }}>
                {indicators.rsi.rsi14}
                {indicators.rsi.rsi14 > 70 ? ' 超买' : indicators.rsi.rsi14 < 30 ? ' 超卖' : ''}
              </span>
            ) : '--'}
          </div>
        </div>
        <div style={{ ...card, flex: 1 }}>
          <div style={{ color: '#888', fontSize: 12 }}>KDJ</div>
          <div style={{ fontSize: 14 }}>
            {indicators?.kdj?.k != null
              ? `K${indicators.kdj.k.toFixed(0)} D${indicators.kdj.d.toFixed(0)} J${indicators.kdj.j.toFixed(0)}`
              : '--'}
          </div>
        </div>
        <div style={{ ...card, flex: 1 }}>
          <div style={{ color: '#888', fontSize: 12 }}>负债率</div>
          <div style={{ fontSize: 14 }}>
            {financial?.debt_ratio?.toFixed(1) || '--'}%
          </div>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat: KlineChart with lightweight-charts, InfoCards with indicators"
```

---

### Task 7: Frontend — DiagnosisPanel (Chat UI + SSE)

- [ ] **Step 1: Create ChatMessage component**

`frontend/src/components/ChatMessage.tsx`:
```typescript
interface Props { role: string; content: string; streaming?: boolean }

export default function ChatMessage({ role, content, streaming }: Props) {
  const isUser = role === 'user'
  return (
    <div style={{
      display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start',
      marginBottom: 8,
    }}>
      <div style={{
        maxWidth: '85%', padding: '8px 12px', borderRadius: 12,
        background: isUser ? '#2563eb' : '#333',
        color: isUser ? '#fff' : '#ddd',
        fontSize: 14, lineHeight: 1.5, whiteSpace: 'pre-wrap',
      }}>
        {!isUser && <span style={{ fontSize: 12, color: '#888' }}>🤖 </span>}
        {content || (streaming ? '思考中...' : '')}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create diagnosis API with SSE**

`frontend/src/api/diagnosis.ts`:
```typescript
interface ChatParams {
  session_id?: string
  skill: string
  model: string
  message: string
  stock_codes: { code: string; name: string }[]
}

interface ChatEvents {
  onSessionId?: (id: string) => void
  onContent?: (chunk: string) => void
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
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.session_id) events.onSessionId?.(data.session_id)
            if (data.content !== undefined) events.onContent?.(data.content)
            if (data.done) events.onDone?.()
          } catch {}
        }
      }
    }
  } catch (e: any) {
    events.onError?.(e.message || 'Connection error')
  }
}
```

- [ ] **Step 3: Create DiagnosisPanel**

`frontend/src/components/DiagnosisPanel.tsx` (replace placeholder):

```typescript
import { useState, useRef, useEffect } from 'react'
import { useApp } from '../contexts/AppContext'
import { chatStream } from '../api/diagnosis'
import ChatMessage from './ChatMessage'
import type { ChatMessage as ChatMsg } from '../types'

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
      session_id: sessionId || undefined,
      skill,
      model: 'deepseek-v4-pro',
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
        setMessages(prev => [...prev, { role: 'assistant', content: `错误: ${err}` }])
        setStreamingContent('')
        setLoading(false)
      },
    })
  }

  return (
    <div style={{ background: '#222', borderRadius: 8, display: 'flex', flexDirection: 'column', height: 'calc(100vh - 80px)' }}>
      <div style={{ padding: 12, borderBottom: '1px solid #333', display: 'flex', alignItems: 'center', gap: 8 }}>
        <select value={skill} onChange={e => setSkill(e.target.value)}
          style={{ background: '#333', color: '#ddd', border: '1px solid #444', borderRadius: 6, padding: '4px 8px' }}>
          {state.skills.map(s => <option key={s.name} value={s.name}>{s.name}</option>)}
        </select>
        <span style={{ color: '#666', fontSize: 12 }}>
          {state.currentStock?.name || '选择股票'}
        </span>
        {sessionId && <span style={{ color: '#555', fontSize: 11, marginLeft: 'auto' }}>#{sessionId.slice(0, 8)}</span>}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
        {messages.length === 0 && !streamingContent && (
          <div style={{ color: '#666', textAlign: 'center', marginTop: 40 }}>
            选择 Skill 和股票后，输入分析问题开始对话
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
```

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: AI diagnosis chat panel with SSE streaming"
```

---

### Task 8: Final Integration — Verify All Endpoints

- [ ] **Step 1: Start both servers and test full flow**

```bash
# Terminal 1
cd backend && .venv/Scripts/python -m uvicorn app.main:app --port 8000

# Terminal 2
cd frontend && npm run dev
```

- [ ] **Step 2: Manual verify**

Open `http://localhost:5173`:
1. Search "茅台" → see stock in dropdown → click
2. Kline chart renders, InfoCards show data
3. In Diagnosis panel, type "分析一下茅台的基本面" → Enter
4. SSE streaming returns AI analysis

- [ ] **Step 3: Commit final**

```bash
git add -A && git commit -m "chore: integration verification, polish"
```

---

## Execution Order

```
Task 1 (indicators + config + DB)
  → Task 2 (indicators API + skills backend)
    → Task 3 (AI diagnosis engine)
      → Task 4 (frontend scaffolding)
        → Task 5 (app shell + search)
          → Task 6 (KlineChart + InfoCards)
            → Task 7 (DiagnosisPanel)
              → Task 8 (integration)
```
