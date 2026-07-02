# 数据层 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the data layer for a stock analysis app — multi-source data ingestion (akshare/yfinance), PostgreSQL caching, unified REST API.

**Architecture:** FastAPI backend with plugin-based datasources. Each datasource implements a common Protocol. A Data Engine handles cache-or-fetch logic with PostgreSQL as the cache layer. APScheduler runs background sync jobs.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0 + asyncpg, Alembic, APScheduler, akshare, yfinance, Pydantic v2, pytest + pytest-asyncio + httpx

## Global Constraints

- Stock codes use unified format: `sh.600519`, `sz.000001`, `us.AAPL`
- All monetary amounts in yuan (CNY) for A-shares, USD for US stocks — stored as-is from source
- Database stores raw data only — no pre-computed indicators
- All API responses are JSON under `/api/v1/`
- Error responses include `request_id` (UUID) for tracing
- Free datasources only for v1 — extensible to paid via plugin interface
- `docker-compose up` must be the only setup step

---

## File Structure

```
hermesStockAgent/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app, lifespan events
│   │   ├── config.py            # Settings from env vars
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── router.py    # APIRouter aggregation
│   │   │       ├── stocks.py    # /stock/{code}/kline, /stock/{code}/realtime
│   │   │       ├── financial.py # /stock/{code}/financial
│   │   │       ├── search.py    # /search
│   │   │       ├── index.py     # /market/index
│   │   │       └── health.py    # /health
│   │   ├── engine/
│   │   │   ├── __init__.py
│   │   │   ├── data_engine.py   # DataEngine: cache-first fetch orchestration
│   │   │   └── scheduler.py     # APScheduler background tasks
│   │   ├── datasources/
│   │   │   ├── __init__.py      # discover_plugins(), registry dict
│   │   │   ├── base.py          # DataSourceProtocol, KlineBar, RealtimeQuote, StockInfo, FinancialReport
│   │   │   ├── akshare.py       # AShareSource
│   │   │   └── yfinance.py      # USStockSource
│   │   └── db/
│   │       ├── __init__.py
│   │       ├── database.py      # async engine, session factory
│   │       ├── models.py        # SQLAlchemy ORM: Stock, DailyKline, Financial, SyncLog
│   │       └── queries.py       # upsert functions, fetch functions
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── alembic.ini
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── .hermes.md
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `docker-compose.yml`
- Create: `backend/requirements.txt`
- Create: `backend/Dockerfile`
- Create: `.env.example`
- Create: `.hermes.md`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`

**Interfaces:**
- Consumes: nothing (foundation)
- Produces: `Settings` class with all config fields (other tasks import from `app.config`)

- [ ] **Step 1: Create docker-compose.yml**

```yaml
version: "3.9"

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: stockapp
      POSTGRES_PASSWORD: stockapp_dev
      POSTGRES_DB: stockdb
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U stockapp -d stockdb"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://stockapp:stockapp_dev@db:5432/stockdb
      LOG_LEVEL: INFO
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

volumes:
  pgdata:
```

- [ ] **Step 2: Create backend/requirements.txt**

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.14.1
pydantic==2.10.4
pydantic-settings==2.7.1
akshare==1.16.72
yfinance==0.2.54
apscheduler==3.11.0
pandas==2.2.3
httpx==0.28.1
pytest==8.3.4
pytest-asyncio==0.25.2
```

- [ ] **Step 3: Create backend/Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 4: Create .env.example**

```
DATABASE_URL=postgresql+asyncpg://stockapp:stockapp_dev@localhost:5432/stockdb
LOG_LEVEL=INFO
```

- [ ] **Step 5: Create .hermes.md**

```markdown
# Hermes Stock Agent

Hermes: when working in this repo, follow these rules.

## Tech Stack
- Backend: FastAPI + SQLAlchemy 2.0 async + PostgreSQL 16
- Python 3.11, use `async/await` for all I/O
- Stock codes: unified format `sh.600519`, `sz.000001`, `us.AAPL`

## Build
- Run backend with: `docker-compose up`
- Run tests with: `docker-compose exec backend pytest -v`
- Lint is optional for now — focus on working code

## Style
- Pydantic v2 for all request/response models
- Use `async def` for all route handlers and DB operations
- Datasource plugins implement `DataSourceProtocol` from `app.datasources.base`
- No pre-computed indicators in DB — store raw data, compute in analysis layer
```

- [ ] **Step 6: Create backend/app/__init__.py**

```python
# Stock Agent Backend
```

- [ ] **Step 7: Create backend/app/config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://stockapp:stockapp_dev@localhost:5432/stockdb"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
```

- [ ] **Step 8: Verify — run docker-compose up, confirm backend starts (will fail with import errors until we add main.py — expected)**

Run: `docker-compose up --build`
Expected: PostgreSQL starts healthy. Backend fails with import error (no `app.main` yet).

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: project scaffolding — docker, config, requirements"
```

---

### Task 2: Data Models and Protocol

**Files:**
- Create: `backend/app/datasources/__init__.py`
- Create: `backend/app/datasources/base.py`

**Interfaces:**
- Consumes: `app.config.settings` (not directly, but type-checking context)
- Produces: `DataSourceProtocol`, `KlineBar`, `RealtimeQuote`, `StockInfo`, `FinancialReport`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_datasource_protocol.py`:

```python
from app.datasources.base import (
    DataSourceProtocol,
    KlineBar,
    RealtimeQuote,
    StockInfo,
    FinancialReport,
)


def test_kline_bar_fields():
    bar = KlineBar(
        date="2026-07-01",
        open=100.0,
        high=105.0,
        low=99.0,
        close=103.5,
        volume=1000000,
        amount=103500000.0,
    )
    assert bar.date == "2026-07-01"
    assert bar.close == 103.5


def test_stock_info_unified_code_format():
    info = StockInfo(
        code="sh.600519",
        name="贵州茅台",
        market="a_share",
        industry="白酒",
    )
    assert info.code.startswith("sh.")


def test_realtime_quote_optional_none():
    # fetch_realtime can return None when unavailable
    assert RealtimeQuote is not None


def test_protocol_defines_required_methods():
    required = [
        "name",
        "markets",
        "search_stocks",
        "fetch_kline",
        "fetch_realtime",
        "fetch_financials",
        "fetch_index",
        "health_check",
    ]
    for method in required:
        assert hasattr(DataSourceProtocol, method), f"Missing: {method}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker-compose exec backend pytest tests/test_datasource_protocol.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create backend/app/datasources/__init__.py**

```python
# Datasource plugin system
```

- [ ] **Step 4: Create backend/app/datasources/base.py**

```python
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class KlineBar:
    """Single OHLCV bar."""
    date: str           # "2026-07-01"
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float


@dataclass
class RealtimeQuote:
    """Latest quote snapshot."""
    code: str
    name: str
    price: float
    change_pct: float
    volume: int
    high: float
    low: float
    timestamp: str      # ISO 8601


@dataclass
class StockInfo:
    """Basic stock identification."""
    code: str           # sh.600519 / us.AAPL
    name: str
    market: str         # "a_share" / "us"
    industry: str


@dataclass
class FinancialReport:
    """Latest financial metrics from a report period."""
    code: str
    report_date: str    # "2026-03-31"
    revenue: float | None = None
    net_profit: float | None = None
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    roe: float | None = None
    debt_ratio: float | None = None
    total_assets: float | None = None
    total_equity: float | None = None


@runtime_checkable
class DataSourceProtocol(Protocol):
    """Interface every datasource plugin must satisfy."""

    @property
    def name(self) -> str: ...

    @property
    def markets(self) -> list[str]: ...

    async def search_stocks(self, keyword: str) -> list[StockInfo]: ...

    async def fetch_kline(
        self, code: str, period: str, start: str, end: str
    ) -> list[KlineBar]: ...

    async def fetch_realtime(self, code: str) -> RealtimeQuote | None: ...

    async def fetch_financials(self, code: str) -> FinancialReport | None: ...

    async def fetch_index(self, code: str) -> RealtimeQuote | None: ...

    def health_check(self) -> bool: ...
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker-compose exec backend pytest tests/test_datasource_protocol.py -v`
Expected: 4 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/datasources/__init__.py backend/app/datasources/base.py backend/tests/test_datasource_protocol.py
git commit -m "feat: data models and datasource protocol"
```

---

### Task 3: Database Setup

**Files:**
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/database.py`
- Create: `backend/app/db/models.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: initial migration in `backend/alembic/versions/`

**Interfaces:**
- Consumes: `app.config.settings` (DATABASE_URL)
- Produces: `get_db()` async generator, `Base` declarative base, ORM models (Stock, DailyKline, Financial, SyncLog)

- [ ] **Step 1: Create backend/app/db/__init__.py**

```python
# Database layer
```

- [ ] **Step 2: Write failing test for DB connection**

Create `backend/tests/test_db.py`:

```python
import pytest
from sqlalchemy import text
from app.db.database import get_engine, get_session


@pytest.mark.asyncio
async def test_engine_creates_async():
    engine = get_engine()
    assert engine is not None


@pytest.mark.asyncio
async def test_can_query_database():
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1
```

Run: `docker-compose exec backend pytest tests/test_db.py -v`
Expected: FAIL

- [ ] **Step 3: Create backend/app/db/database.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import settings

_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(settings.database_url, echo=False)
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _session_factory


async def get_db():
    """FastAPI dependency: yields an async session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
```

- [ ] **Step 4: Create backend/app/db/models.py**

```python
from sqlalchemy import Column, String, Date, Integer, BigInteger, Numeric, Text, DateTime, PrimaryKeyConstraint
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class Stock(Base):
    __tablename__ = "stocks"

    code = Column(String(20), primary_key=True)
    name = Column(String(100), nullable=False)
    market = Column(String(10), nullable=False)
    industry = Column(String(50))
    list_date = Column(Date)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class DailyKline(Base):
    __tablename__ = "stock_daily"
    __table_args__ = (
        PrimaryKeyConstraint("code", "trade_date"),
    )

    code = Column(String(20), nullable=False, index=True)
    trade_date = Column(Date, nullable=False)
    open = Column(Numeric(12, 4))
    high = Column(Numeric(12, 4))
    low = Column(Numeric(12, 4))
    close = Column(Numeric(12, 4))
    volume = Column(BigInteger)
    amount = Column(Numeric(20, 2))


class Financial(Base):
    __tablename__ = "stock_financial"
    __table_args__ = (
        PrimaryKeyConstraint("code", "report_date"),
    )

    code = Column(String(20), nullable=False, index=True)
    report_date = Column(Date, nullable=False)
    revenue = Column(Numeric(20, 2))
    net_profit = Column(Numeric(20, 2))
    pe_ratio = Column(Numeric(12, 4))
    pb_ratio = Column(Numeric(12, 4))
    roe = Column(Numeric(8, 4))
    debt_ratio = Column(Numeric(8, 4))
    total_assets = Column(Numeric(20, 2))
    total_equity = Column(Numeric(20, 2))


class SyncLog(Base):
    __tablename__ = "sync_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(20), nullable=False)
    data_type = Column(String(20), nullable=False)
    code = Column(String(20))
    status = Column(String(10), nullable=False)
    rows_count = Column(Integer, default=0)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    error_msg = Column(Text)
```

- [ ] **Step 5: Run tests — DB connection works**

Run: `docker-compose exec backend pytest tests/test_db.py -v`
Expected: 2 PASS

- [ ] **Step 6: Create backend/alembic.ini**

```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://stockapp:stockapp_dev@localhost:5432/stockdb

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 7: Create backend/alembic/env.py**

```python
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from app.db.models import Base
from app.config import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online():
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 8: Generate and run initial migration**

```bash
docker-compose exec backend alembic revision --autogenerate -m "init_stock_tables"
docker-compose exec backend alembic upgrade head
```

- [ ] **Step 9: Verify — tables exist**

Run: `docker-compose exec db psql -U stockapp -d stockdb -c "\dt"`
Expected: lists stocks, stock_daily, stock_financial, sync_log, alembic_version

- [ ] **Step 10: Commit**

```bash
git add backend/app/db/ backend/alembic.ini backend/alembic/ backend/tests/test_db.py
git commit -m "feat: database models and alembic migration"
```

---

### Task 4: DB Queries Layer

**Files:**
- Create: `backend/app/db/queries.py`

**Interfaces:**
- Consumes: `app.db.models` (ORM classes), `app.db.database.get_db` (session)
- Produces: `upsert_stock()`, `upsert_daily_klines()`, `upsert_financials()`, `get_daily_klines()`, `get_latest_financial()`, `get_max_trade_date()`, `search_stocks_db()`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_queries.py`:

```python
import pytest
from app.db.queries import upsert_stock, get_daily_klines
from app.db.database import get_session


@pytest.mark.asyncio
async def test_upsert_and_query_stock():
    async with get_session() as session:
        # Upsert
        await upsert_stock(session, "sh.600519", "贵州茅台", "a_share", "白酒")
        await session.commit()

        # Query back
        from sqlalchemy import select
        from app.db.models import Stock
        result = await session.execute(
            select(Stock).where(Stock.code == "sh.600519")
        )
        stock = result.scalar_one()
        assert stock.name == "贵州茅台"
```

Run: `docker-compose exec backend pytest tests/test_queries.py -v`
Expected: FAIL

- [ ] **Step 2: Create backend/app/db/queries.py**

```python
from datetime import date
from sqlalchemy import select, func, or_
from sqlalchemy.dialects.postgresql import insert
from app.db.models import Stock, DailyKline, Financial, SyncLog


async def upsert_stock(session, code: str, name: str, market: str, industry: str = ""):
    stmt = insert(Stock).values(
        code=code, name=name, market=market, industry=industry
    ).on_conflict_do_update(
        index_elements=["code"],
        set_={"name": name, "industry": industry, "updated_at": func.now()},
    )
    await session.execute(stmt)


async def upsert_daily_klines(session, code: str, bars: list[dict]):
    """bars: list of {date, open, high, low, close, volume, amount}"""
    for bar in bars:
        stmt = insert(DailyKline).values(code=code, **bar).on_conflict_do_update(
            index_elements=["code", "trade_date"],
            set_={
                "open": bar["open"], "high": bar["high"],
                "low": bar["low"], "close": bar["close"],
                "volume": bar["volume"], "amount": bar["amount"],
            },
        )
        await session.execute(stmt)


async def upsert_financials(session, code: str, report: dict):
    stmt = insert(Financial).values(code=code, **report).on_conflict_do_update(
        index_elements=["code", "report_date"],
        set_={k: v for k, v in report.items() if k != "report_date"},
    )
    await session.execute(stmt)


async def get_daily_klines(session, code: str, start: str, end: str) -> list[dict]:
    result = await session.execute(
        select(DailyKline)
        .where(DailyKline.code == code)
        .where(DailyKline.trade_date >= start)
        .where(DailyKline.trade_date <= end)
        .order_by(DailyKline.trade_date.asc())
    )
    rows = result.scalars().all()
    return [
        {
            "date": str(r.trade_date),
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": int(r.volume),
            "amount": float(r.amount),
        }
        for r in rows
    ]


async def get_max_trade_date(session, code: str) -> date | None:
    result = await session.execute(
        select(func.max(DailyKline.trade_date)).where(DailyKline.code == code)
    )
    return result.scalar()


async def get_latest_financial(session, code: str) -> dict | None:
    result = await session.execute(
        select(Financial)
        .where(Financial.code == code)
        .order_by(Financial.report_date.desc())
        .limit(1)
    )
    row = result.scalar()
    if row is None:
        return None
    return {
        "report_date": str(row.report_date),
        "revenue": float(row.revenue) if row.revenue else None,
        "net_profit": float(row.net_profit) if row.net_profit else None,
        "pe_ratio": float(row.pe_ratio) if row.pe_ratio else None,
        "pb_ratio": float(row.pb_ratio) if row.pb_ratio else None,
        "roe": float(row.roe) if row.roe else None,
        "debt_ratio": float(row.debt_ratio) if row.debt_ratio else None,
        "total_assets": float(row.total_assets) if row.total_assets else None,
        "total_equity": float(row.total_equity) if row.total_equity else None,
    }


async def search_stocks_db(session, keyword: str) -> list[dict]:
    pattern = f"%{keyword}%"
    result = await session.execute(
        select(Stock).where(
            or_(Stock.code.ilike(pattern), Stock.name.ilike(pattern))
        ).limit(20)
    )
    rows = result.scalars().all()
    return [
        {
            "code": r.code,
            "name": r.name,
            "market": r.market,
            "industry": r.industry or "",
        }
        for r in rows
    ]


async def log_sync(session, source: str, data_type: str, code: str | None,
                   status: str, rows_count: int = 0, error_msg: str | None = None):
    entry = SyncLog(
        source=source, data_type=data_type, code=code,
        status=status, rows_count=rows_count, error_msg=error_msg,
        started_at=func.now(), finished_at=func.now(),
    )
    session.add(entry)
    await session.flush()
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `docker-compose exec backend pytest tests/test_queries.py -v`
Expected: 1 PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/queries.py backend/tests/test_queries.py
git commit -m "feat: DB queries layer — upsert/fetch/search for stocks and klines"
```

---

### Task 5: A-Share Datasource (akshare)

**Files:**
- Create: `backend/app/datasources/akshare.py`

**Interfaces:**
- Consumes: `app.datasources.base` (DataSourceProtocol, KlineBar, etc.)
- Produces: `AShareSource` class implementing DataSourceProtocol

- [ ] **Step 1: Create backend/app/datasources/akshare.py**

```python
"""A-share datasource via akshare."""
from datetime import datetime
import akshare as ak
from app.datasources.base import (
    DataSourceProtocol, KlineBar, RealtimeQuote, StockInfo, FinancialReport,
)


class AShareSource:
    """A-share (沪深) datasource using akshare."""

    @property
    def name(self) -> str:
        return "akshare"

    @property
    def markets(self) -> list[str]:
        return ["a_share"]

    async def search_stocks(self, keyword: str) -> list[StockInfo]:
        import asyncio
        loop = asyncio.get_event_loop()

        def _search():
            # akshare stock_info_a_code_name is synchronous
            df = ak.stock_info_a_code_name()
            matches = df[
                df["code"].str.contains(keyword) |
                df["name"].str.contains(keyword)
            ]
            results = []
            for _, row in matches.head(20).iterrows():
                raw_code = str(row["code"])
                # Determine sh/sz prefix
                if raw_code.startswith("6"):
                    code = f"sh.{raw_code}"
                else:
                    code = f"sz.{raw_code}"
                results.append(StockInfo(
                    code=code, name=row["name"],
                    market="a_share", industry="",
                ))
            return results

        return await loop.run_in_executor(None, _search)

    async def fetch_kline(
        self, code: str, period: str = "daily",
        start: str = "2020-01-01", end: str | None = None,
    ) -> list[KlineBar]:
        import asyncio
        loop = asyncio.get_event_loop()

        if end is None:
            end = datetime.now().strftime("%Y%m%d")

        # Convert code: sh.600519 → 600519
        raw_code = code.split(".")[-1]

        def _fetch():
            if period == "daily":
                df = ak.stock_zh_a_hist(
                    symbol=raw_code, period="daily",
                    start_date=start.replace("-", ""),
                    end_date=end.replace("-", ""),
                    adjust="qfq",  # forward-adjusted
                )
            elif period in ("weekly", "monthly"):
                df = ak.stock_zh_a_hist(
                    symbol=raw_code, period=period,
                    start_date=start.replace("-", ""),
                    end_date=end.replace("-", ""),
                    adjust="qfq",
                )
            else:
                return []

            bars = []
            for _, row in df.iterrows():
                bars.append(KlineBar(
                    date=str(row["日期"])[:10],
                    open=float(row["开盘"]),
                    high=float(row["最高"]),
                    low=float(row["最低"]),
                    close=float(row["收盘"]),
                    volume=int(row["成交量"]),
                    amount=float(row["成交额"]),
                ))
            return bars

        return await loop.run_in_executor(None, _fetch)

    async def fetch_realtime(self, code: str) -> RealtimeQuote | None:
        import asyncio
        loop = asyncio.get_event_loop()

        raw_code = code.split(".")[-1]

        def _fetch():
            try:
                df = ak.stock_zh_a_spot_em()
                row = df[df["代码"] == raw_code]
                if row.empty:
                    return None
                r = row.iloc[0]
                return RealtimeQuote(
                    code=code,
                    name=str(r["名称"]),
                    price=float(r["最新价"]),
                    change_pct=float(r["涨跌幅"]),
                    volume=int(r["成交量"]),
                    high=float(r["最高"]),
                    low=float(r["最低"]),
                    timestamp=datetime.now().isoformat(),
                )
            except Exception:
                return None

        return await loop.run_in_executor(None, _fetch)

    async def fetch_financials(self, code: str) -> FinancialReport | None:
        import asyncio
        loop = asyncio.get_event_loop()

        raw_code = code.split(".")[-1]

        def _fetch():
            try:
                df = ak.stock_financial_abstract_ths(symbol=raw_code, indicator="按报告期")
                if df.empty:
                    return None
                latest = df.iloc[0]
                return FinancialReport(
                    code=code,
                    report_date=str(latest["报告期"]),
                    revenue=_safe_float(latest.get("营业总收入")),
                    net_profit=_safe_float(latest.get("净利润")),
                    pe_ratio=None,  # akshare doesn't provide PE in this endpoint
                    pb_ratio=None,
                    roe=_safe_float(latest.get("净资产收益率")),
                    debt_ratio=_safe_float(latest.get("资产负债率")),
                    total_assets=_safe_float(latest.get("资产总计")),
                    total_equity=_safe_float(latest.get("股东权益合计")),
                )
            except Exception:
                return None

        return await loop.run_in_executor(None, _fetch)

    async def fetch_index(self, code: str) -> RealtimeQuote | None:
        import asyncio
        loop = asyncio.get_event_loop()

        raw_code = code.split(".")[-1]

        def _fetch():
            try:
                df = ak.stock_zh_index_spot_em()
                row = df[df["代码"] == raw_code]
                if row.empty:
                    return None
                r = row.iloc[0]
                return RealtimeQuote(
                    code=code,
                    name=str(r["名称"]),
                    price=float(r["最新价"]),
                    change_pct=float(r["涨跌幅"]),
                    volume=int(r["成交量"]) if r.get("成交量") else 0,
                    high=float(r["最高"]),
                    low=float(r["最低"]),
                    timestamp=datetime.now().isoformat(),
                )
            except Exception:
                return None

        return await loop.run_in_executor(None, _fetch)

    def health_check(self) -> bool:
        try:
            ak.stock_info_a_code_name()
            return True
        except Exception:
            return False


def _safe_float(val) -> float | None:
    """Convert a possibly-NaN or string value to float or None."""
    import math
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/datasources/akshare.py
git commit -m "feat: A-share datasource plugin via akshare"
```

---

### Task 6: US Stock Datasource (yfinance)

**Files:**
- Create: `backend/app/datasources/yfinance.py`

**Interfaces:**
- Consumes: `app.datasources.base`
- Produces: `USStockSource` class implementing DataSourceProtocol

- [ ] **Step 1: Create backend/app/datasources/yfinance.py**

```python
"""US stock datasource via yfinance."""
from datetime import datetime
import yfinance as yf
from app.datasources.base import (
    DataSourceProtocol, KlineBar, RealtimeQuote, StockInfo, FinancialReport,
)


class USStockSource:
    """US stock datasource using yfinance."""

    @property
    def name(self) -> str:
        return "yfinance"

    @property
    def markets(self) -> list[str]:
        return ["us"]

    async def search_stocks(self, keyword: str) -> list[StockInfo]:
        import asyncio
        loop = asyncio.get_event_loop()

        def _search():
            # yfinance ticker search
            try:
                ticker = yf.Ticker(keyword.upper())
                info = ticker.info or {}
                if not info:
                    return []
                return [StockInfo(
                    code=f"us.{keyword.upper()}",
                    name=info.get("longName") or info.get("shortName", ""),
                    market="us",
                    industry=info.get("industry", ""),
                )]
            except Exception:
                return []

        return await loop.run_in_executor(None, _search)

    async def fetch_kline(
        self, code: str, period: str = "daily",
        start: str = "2020-01-01", end: str | None = None,
    ) -> list[KlineBar]:
        import asyncio
        loop = asyncio.get_event_loop()

        ticker_symbol = code.split(".")[-1]  # us.AAPL → AAPL

        interval_map = {"daily": "1d", "weekly": "1wk", "monthly": "1mo"}
        interval = interval_map.get(period, "1d")

        if end is None:
            end = datetime.now().strftime("%Y-%m-%d")

        def _fetch():
            ticker = yf.Ticker(ticker_symbol)
            df = ticker.history(start=start, end=end, interval=interval)
            if df.empty:
                return []
            bars = []
            for idx, row in df.iterrows():
                bars.append(KlineBar(
                    date=idx.strftime("%Y-%m-%d"),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=int(row["Volume"]),
                    amount=float(row["Close"] * row["Volume"]),
                ))
            return bars

        return await loop.run_in_executor(None, _fetch)

    async def fetch_realtime(self, code: str) -> RealtimeQuote | None:
        import asyncio
        loop = asyncio.get_event_loop()

        ticker_symbol = code.split(".")[-1]

        def _fetch():
            try:
                ticker = yf.Ticker(ticker_symbol)
                info = ticker.info or {}
                if not info:
                    return None
                return RealtimeQuote(
                    code=code,
                    name=info.get("shortName", ticker_symbol),
                    price=float(info.get("currentPrice", info.get("regularMarketPrice", 0))),
                    change_pct=float(info.get("regularMarketChangePercent", 0)),
                    volume=int(info.get("volume", 0)),
                    high=float(info.get("dayHigh", 0)),
                    low=float(info.get("dayLow", 0)),
                    timestamp=datetime.now().isoformat(),
                )
            except Exception:
                return None

        return await loop.run_in_executor(None, _fetch)

    async def fetch_financials(self, code: str) -> FinancialReport | None:
        import asyncio
        loop = asyncio.get_event_loop()

        ticker_symbol = code.split(".")[-1]

        def _fetch():
            try:
                ticker = yf.Ticker(ticker_symbol)
                info = ticker.info or {}
                if not info:
                    return None
                return FinancialReport(
                    code=code,
                    report_date=datetime.now().strftime("%Y-%m-%d"),
                    revenue=_safe_float(info.get("totalRevenue")),
                    net_profit=_safe_float(info.get("netIncomeToCommon")),
                    pe_ratio=_safe_float(info.get("trailingPE")),
                    pb_ratio=_safe_float(info.get("priceToBook")),
                    roe=_safe_float(info.get("returnOnEquity")),
                    debt_ratio=_safe_float(info.get("debtToEquity")),
                    total_assets=_safe_float(info.get("totalAssets")),
                    total_equity=_safe_float(info.get("totalStockholderEquity")),
                )
            except Exception:
                return None

        return await loop.run_in_executor(None, _fetch)

    async def fetch_index(self, code: str) -> RealtimeQuote | None:
        """Fetch market index. Code format: us.^GSPC, us.^IXIC, us.^DJI"""
        import asyncio
        loop = asyncio.get_event_loop()

        ticker_symbol = code.split(".")[-1]

        def _fetch():
            try:
                ticker = yf.Ticker(ticker_symbol)
                info = ticker.info or {}
                if not info:
                    # Fallback: try fast_info
                    try:
                        fast = ticker.fast_info
                        return RealtimeQuote(
                            code=code,
                            name=ticker_symbol,
                            price=float(fast.get("lastPrice", 0)),
                            change_pct=0.0,
                            volume=0,
                            high=float(fast.get("dayHigh", 0)),
                            low=float(fast.get("dayLow", 0)),
                            timestamp=datetime.now().isoformat(),
                        )
                    except Exception:
                        return None
                return RealtimeQuote(
                    code=code,
                    name=info.get("shortName", ticker_symbol),
                    price=float(info.get("regularMarketPrice", 0)),
                    change_pct=float(info.get("regularMarketChangePercent", 0)),
                    volume=int(info.get("regularMarketVolume", 0)),
                    high=float(info.get("regularMarketDayHigh", 0)),
                    low=float(info.get("regularMarketDayLow", 0)),
                    timestamp=datetime.now().isoformat(),
                )
            except Exception:
                return None

        return await loop.run_in_executor(None, _fetch)

    def health_check(self) -> bool:
        try:
            ticker = yf.Ticker("AAPL")
            info = ticker.info
            return info is not None and len(info) > 0
        except Exception:
            return False


def _safe_float(val) -> float | None:
    import math
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/datasources/yfinance.py
git commit -m "feat: US stock datasource plugin via yfinance"
```

---

### Task 7: Plugin Auto-Discovery

**Files:**
- Modify: `backend/app/datasources/__init__.py`

**Interfaces:**
- Consumes: `app.datasources.akshare.AShareSource`, `app.datasources.yfinance.USStockSource`
- Produces: `get_sources()` → dict[str, DataSourceProtocol], `get_source_for_market(market: str)`

- [ ] **Step 1: Rewrite backend/app/datasources/__init__.py**

```python
"""Datasource plugin auto-discovery and registry."""
from app.datasources.akshare import AShareSource
from app.datasources.yfinance import USStockSource

_registry: dict[str, object] = {}


def _build_registry():
    """Discover and register all datasource plugins."""
    global _registry
    if _registry:
        return

    a_source = AShareSource()
    us_source = USStockSource()

    _registry["akshare"] = a_source
    _registry["yfinance"] = us_source


def get_sources() -> dict[str, object]:
    """Return all registered datasources keyed by name."""
    _build_registry()
    return _registry


def get_source_for_market(market: str) -> object | None:
    """Return the first datasource supporting the given market."""
    _build_registry()
    for source in _registry.values():
        if market in source.markets:
            return source
    return None


def get_healthy_sources() -> list[str]:
    """Return names of datasources that pass health check."""
    _build_registry()
    return [name for name, src in _registry.items() if src.health_check()]


_initial_registry = _build_registry  # defer to first access
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/datasources/__init__.py
git commit -m "feat: datasource plugin auto-discovery registry"
```

---

### Task 8: Data Engine

**Files:**
- Create: `backend/app/engine/__init__.py`
- Create: `backend/app/engine/data_engine.py`

**Interfaces:**
- Consumes: `app.datasources` (registry), `app.db.queries`, `app.db.database`
- Produces: `DataEngine` class with `get_klines()`, `get_realtime()`, `get_financial()`, `get_index()`, `search()`, `health()`

- [ ] **Step 1: Create backend/app/engine/__init__.py**

```python
# Data engine
```

- [ ] **Step 2: Create backend/app/engine/data_engine.py**

```python
"""Data Engine: cache-first fetch orchestration."""
import logging
from datetime import date, timedelta
from app.db.database import get_session_factory
from app.db import queries
from app.datasources import get_source_for_market, get_healthy_sources

logger = logging.getLogger(__name__)


class DataEngine:
    """Orchestrates data fetching with PostgreSQL caching."""

    async def get_klines(
        self, code: str, period: str, start: str, end: str,
    ) -> tuple[list[dict], str | None]:
        """Return kline data and optional warning. Caches misses via datasource."""
        factory = get_session_factory()
        async with factory() as session:
            cached = await queries.get_daily_klines(session, code, start, end)

            if cached and len(cached) > 0:
                return cached, None

            # Cache miss — fetch from source
            market = self._market_from_code(code)
            source = get_source_for_market(market)
            if source is None:
                return [], f"No datasource for market: {market}"

            try:
                bars = await source.fetch_kline(code, period, start, end)
                if not bars:
                    return [], None

                bar_dicts = [
                    {
                        "trade_date": b.date,
                        "open": b.open, "high": b.high, "low": b.low,
                        "close": b.close, "volume": b.volume, "amount": b.amount,
                    }
                    for b in bars
                ]
                await queries.upsert_daily_klines(session, code, bar_dicts)
                await session.commit()

                return [
                    {
                        "date": b.date,
                        "open": b.open, "high": b.high, "low": b.low,
                        "close": b.close, "volume": b.volume, "amount": b.amount,
                    }
                    for b in bars
                ], None
            except Exception as e:
                logger.error(f"Failed to fetch klines for {code}: {e}")
                return [], f"Data source temporarily unavailable for {code}"

    async def get_realtime(self, code: str) -> tuple[dict | None, str | None]:
        market = self._market_from_code(code)
        source = get_source_for_market(market)
        if source is None:
            return None, f"No datasource for market: {market}"

        try:
            quote = await source.fetch_realtime(code)
            if quote is None:
                return None, None
            return {
                "code": quote.code,
                "name": quote.name,
                "price": quote.price,
                "change_pct": quote.change_pct,
                "volume": quote.volume,
                "high": quote.high,
                "low": quote.low,
                "timestamp": quote.timestamp,
            }, None
        except Exception as e:
            logger.error(f"Failed to fetch realtime for {code}: {e}")
            return None, f"Data source temporarily unavailable"

    async def get_financial(self, code: str) -> tuple[dict | None, str | None]:
        factory = get_session_factory()
        async with factory() as session:
            cached = await queries.get_latest_financial(session, code)
            if cached:
                return cached, None

            market = self._market_from_code(code)
            source = get_source_for_market(market)
            if source is None:
                return None, f"No datasource for market: {market}"

            try:
                report = await source.fetch_financials(code)
                if report is None:
                    return None, None

                report_dict = {
                    "report_date": report.report_date,
                    "revenue": report.revenue,
                    "net_profit": report.net_profit,
                    "pe_ratio": report.pe_ratio,
                    "pb_ratio": report.pb_ratio,
                    "roe": report.roe,
                    "debt_ratio": report.debt_ratio,
                    "total_assets": report.total_assets,
                    "total_equity": report.total_equity,
                }
                await queries.upsert_financials(session, code, report_dict)
                await session.commit()
                return report_dict, None
            except Exception as e:
                logger.error(f"Failed to fetch financials for {code}: {e}")
                return None, f"Data source temporarily unavailable"

    async def get_index(self, codes: list[str]) -> tuple[list[dict], str | None]:
        results = []
        warnings = []
        for code in codes:
            data, warn = await self.get_realtime(code)
            if data:
                results.append(data)
            if warn:
                warnings.append(warn)
        return results, "; ".join(warnings) if warnings else None

    async def search(self, keyword: str) -> tuple[list[dict], str | None]:
        factory = get_session_factory()
        async with factory() as session:
            db_results = await queries.search_stocks_db(session, keyword)
            if db_results:
                return db_results, None

        all_results = []
        from app.datasources import get_sources
        for source in get_sources().values():
            try:
                stocks = await source.search_stocks(keyword)
                for s in stocks:
                    all_results.append({
                        "code": s.code,
                        "name": s.name,
                        "market": s.market,
                        "industry": s.industry,
                    })
            except Exception as e:
                logger.warning(f"Search failed for source {source.name}: {e}")

        return all_results[:20], None

    async def health(self) -> dict:
        healthy = get_healthy_sources()

        factory = get_session_factory()
        try:
            async with factory() as session:
                from sqlalchemy import text
                await session.execute(text("SELECT 1"))
                db_status = "connected"
        except Exception:
            db_status = "disconnected"

        return {
            "status": "ok" if healthy and db_status == "connected" else "degraded",
            "datasources": {
                name: "healthy" if name in healthy else "unhealthy"
                for name in ["akshare", "yfinance"]
            },
            "database": db_status,
        }

    @staticmethod
    def _market_from_code(code: str) -> str:
        if code.startswith("us."):
            return "us"
        return "a_share"


# Singleton
engine = DataEngine()
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/engine/
git commit -m "feat: data engine with cache-first fetch orchestration"
```

---

### Task 9: API Endpoints

**Files:**
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/v1/__init__.py`
- Create: `backend/app/api/v1/router.py`
- Create: `backend/app/api/v1/stocks.py`
- Create: `backend/app/api/v1/financial.py`
- Create: `backend/app/api/v1/search.py`
- Create: `backend/app/api/v1/index.py`
- Create: `backend/app/api/v1/health.py`

**Interfaces:**
- Consumes: `app.engine.data_engine.engine`
- Produces: FastAPI route handlers for all `/api/v1/` endpoints

- [ ] **Step 1: Create backend/app/api/__init__.py**

```python
# API layer
```

- [ ] **Step 2: Create backend/app/api/v1/__init__.py**

```python
# API v1
```

- [ ] **Step 3: Create backend/app/api/v1/router.py**

```python
from fastapi import APIRouter
from . import stocks, financial, search, index, health

router = APIRouter(prefix="/api/v1")
router.include_router(stocks.router)
router.include_router(financial.router)
router.include_router(search.router)
router.include_router(index.router)
router.include_router(health.router)
```

- [ ] **Step 4: Create backend/app/api/v1/stocks.py**

```python
"""Stock kline and realtime endpoints."""
import uuid
from fastapi import APIRouter, Query, HTTPException
from app.engine.data_engine import engine

router = APIRouter(tags=["stocks"])


@router.get("/stock/{code}/kline")
async def get_stock_kline(
    code: str,
    period: str = Query("daily", pattern=r"^(daily|weekly|monthly)$"),
    start: str = Query("2024-01-01"),
    end: str = Query("2026-12-31"),
):
    data, warning = await engine.get_klines(code, period, start, end)
    result = {
        "code": code,
        "period": period,
        "data": data,
        "count": len(data),
    }
    if warning:
        result["warning"] = warning
    return result


@router.get("/stock/{code}/realtime")
async def get_stock_realtime(code: str):
    data, warning = await engine.get_realtime(code)
    if data is None and warning is None:
        raise HTTPException(status_code=404, detail={
            "error": f"未找到股票 {code}",
            "request_id": str(uuid.uuid4()),
        })
    if data is None:
        raise HTTPException(status_code=503, detail={
            "error": warning,
            "request_id": str(uuid.uuid4()),
        })
    if warning:
        data["warning"] = warning
    return data
```

- [ ] **Step 5: Create backend/app/api/v1/financial.py**

```python
"""Financial data endpoint."""
import uuid
from fastapi import APIRouter, HTTPException
from app.engine.data_engine import engine

router = APIRouter(tags=["financial"])


@router.get("/stock/{code}/financial")
async def get_stock_financial(code: str):
    data, warning = await engine.get_financial(code)
    if data is None:
        raise HTTPException(status_code=404, detail={
            "error": f"未找到 {code} 的财务数据",
            "request_id": str(uuid.uuid4()),
        })
    result = {
        "code": code,
        "reports": [data],
    }
    if warning:
        result["warning"] = warning
    return result
```

- [ ] **Step 6: Create backend/app/api/v1/search.py**

```python
"""Stock search endpoint."""
from fastapi import APIRouter, Query
from app.engine.data_engine import engine

router = APIRouter(tags=["search"])


@router.get("/search")
async def search_stocks(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    market: str | None = Query(None, pattern=r"^(a_share|us)$"),
):
    results, warning = await engine.search(q)
    if market:
        results = [r for r in results if r["market"] == market]
    return {"results": results, "count": len(results)}
```

- [ ] **Step 7: Create backend/app/api/v1/index.py**

```python
"""Market index endpoint."""
from fastapi import APIRouter, Query
from app.engine.data_engine import engine

router = APIRouter(tags=["index"])


@router.get("/market/index")
async def get_market_index(
    codes: str = Query("sh.000001,us.^GSPC", description="逗号分隔的指数代码"),
):
    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    indices, warning = await engine.get_index(code_list)
    result = {"indices": indices}
    if warning:
        result["warning"] = warning
    return result
```

- [ ] **Step 8: Create backend/app/api/v1/health.py**

```python
"""Health check endpoint."""
from fastapi import APIRouter
from app.engine.data_engine import engine

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return await engine.health()
```

- [ ] **Step 9: Commit**

```bash
git add backend/app/api/
git commit -m "feat: REST API endpoints for stocks, search, index, health"
```

---

### Task 10: FastAPI App Entry Point + Scheduler

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/app/engine/scheduler.py`

**Interfaces:**
- Consumes: `app.api.v1.router`, `app.engine.data_engine`, `app.db.database`
- Produces: FastAPI `app` instance, background sync scheduler

- [ ] **Step 1: Create backend/app/engine/scheduler.py**

```python
"""Background sync scheduler using APScheduler."""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.db.database import get_session_factory
from app.db import queries
from app.datasources import get_sources

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def sync_all_daily_klines():
    """Sync latest daily klines for tracked stocks."""
    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select
        from app.db.models import Stock
        result = await session.execute(select(Stock.code))
        codes = [row[0] for row in result.fetchall()]

    for code in codes:
        market = "a_share" if code.startswith("sh.") or code.startswith("sz.") else "us"
        from app.datasources import get_source_for_market
        source = get_source_for_market(market)
        if source is None:
            continue

        try:
            from datetime import date
            start = str(date.today())
            end = str(date.today())
            factory2 = get_session_factory()
            async with factory2() as s2:
                max_date = await queries.get_max_trade_date(s2, code)
            if max_date:
                from datetime import timedelta
                start = str(max_date + timedelta(days=1))

            bars = await source.fetch_kline(code, "daily", start, end)
            if bars:
                bar_dicts = [
                    {
                        "trade_date": b.date,
                        "open": b.open, "high": b.high, "low": b.low,
                        "close": b.close, "volume": b.volume, "amount": b.amount,
                    }
                    for b in bars
                ]
                async with factory2() as s2:
                    await queries.upsert_daily_klines(s2, code, bar_dicts)
                    await queries.log_sync(s2, source.name, "kline", code, "done", len(bar_dicts))
                    await s2.commit()
                logger.info(f"Synced {len(bar_dicts)} bars for {code}")
        except Exception as e:
            logger.error(f"Sync failed for {code}: {e}")


def start_scheduler():
    scheduler.add_job(
        sync_all_daily_klines,
        "cron",
        hour=16, minute=0,
        id="daily_kline_sync",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Background scheduler started")
```

- [ ] **Step 2: Create backend/app/main.py**

```python
"""FastAPI application entry point."""
import uuid
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.v1.router import router as v1_router
from app.engine.scheduler import start_scheduler
from app.engine.data_engine import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Stock Agent backend...")
    start_scheduler()
    # Warm up: run health check
    health = await engine.health()
    logger.info(f"Startup health: {health}")
    yield
    # Shutdown
    logger.info("Shutting down...")


app = FastAPI(
    title="Stock Agent API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "内部错误",
            "request_id": str(uuid.uuid4()),
        },
    )


@app.get("/")
async def root():
    return {"app": "Stock Agent", "version": "0.1.0", "docs": "/docs"}
```

- [ ] **Step 3: Verify — docker-compose up, test /health**

Run: `docker-compose up --build -d`
Then: `curl http://localhost:8000/health`
Expected:
```json
{"status":"ok","datasources":{"akshare":"healthy","yfinance":"healthy"},"database":"connected"}
```

- [ ] **Step 4: Verify — test /search**

Run: `curl "http://localhost:8000/api/v1/search?q=茅台"`
Expected: returns stock results with code, name, market, industry

- [ ] **Step 5: Verify — test /stock/{code}/kline**

Run: `curl "http://localhost:8000/api/v1/stock/sh.600519/kline?period=daily&start=2026-01-01&end=2026-06-30"`
Expected: returns kline JSON array (may take a few seconds on first call — fetching from akshare)

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/app/engine/scheduler.py
git commit -m "feat: FastAPI entry point with background scheduler"
```

---

### Task 11: Integration Verification

**Files:** none (verification only)

- [ ] **Step 1: Run full integration test**

Create `backend/tests/test_api_integration.py`:

```python
"""Integration tests against running backend."""
import pytest
import httpx


BASE_URL = "http://localhost:8000"


@pytest.mark.asyncio
async def test_health_endpoint():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "datasources" in data
        assert "database" in data


@pytest.mark.asyncio
async def test_search_returns_results():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/api/v1/search?q=茅台")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) > 0
        assert data["results"][0]["code"].startswith("sh.")


@pytest.mark.asyncio
async def test_kline_endpoint():
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{BASE_URL}/api/v1/stock/sh.600519/kline",
            params={"period": "daily", "start": "2026-06-01", "end": "2026-06-30"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        if data["data"]:
            bar = data["data"][0]
            assert "date" in bar
            assert "close" in bar


@pytest.mark.asyncio
async def test_swagger_accessible():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/docs")
        assert resp.status_code == 200
```

Run: `pip install httpx && pytest tests/test_api_integration.py -v`
Expected: 4 PASS

- [ ] **Step 2: Verify Swagger UI**

Open `http://localhost:8000/docs` in browser and test each endpoint interactively.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_api_integration.py
git commit -m "test: integration tests for all API endpoints"
```

---

## Execution Order

Tasks must run sequentially — each depends on the previous:

```
Task 1 (scaffolding)
  → Task 2 (data models)
    → Task 3 (database setup)
      → Task 4 (queries layer)
        → Task 5 (akshare plugin)
        → Task 6 (yfinance plugin)
          → Task 7 (plugin registry)
            → Task 8 (data engine)
              → Task 9 (API endpoints)
                → Task 10 (main + scheduler)
                  → Task 11 (integration verification)
```
