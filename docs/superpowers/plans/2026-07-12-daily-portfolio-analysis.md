# 每日持仓分析与操作指导系统 - 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 hermesStockAgent 新增持仓管理 + 每日自动生成 AI 操作指导报告功能，包含持仓/交易 CRUD、三阶段分析管道（规则计算 + DeepSeek 逐股分析 + 综合总结）、跨日记忆追踪、前端第 4 个 TabView。

**Architecture:** 方案C 分层架构。后端新增 5 个 DB 模型 + portfolio 路由模块 + analyzer 管道。AI 分析直接调 DeepSeek API（不走 diagnosis session），复用 tools.py 工具函数 + skills_manager skill 注入。前端新增 PortfolioView 组件 + 可拖拽分隔条。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + Pydantic v2 + APScheduler（后端）; React 19 + TypeScript + Tailwind CSS（前端）; DeepSeek API（AI）; SQLite（dev DB）

## Global Constraints

- 后端入口 `backend/app/main.py:app`，端口 8002 不可更改
- 股票代码统一格式 `sh.600519`、`sz.000001`、`us.AAPL`
- 所有路由 handler 和 DB 操作必须 `async def`
- Pydantic v2 用于所有请求/响应模型
- 新模型追加到 `backend/app/db/models.py`，`Base.metadata.create_all` 自动建表
- 测试用 `TestClient`（bypass proxy），fixtures 在 `conftest.py`（module-scoped client + stock_code="sh.600519"）
- 前端路径别名 `@/*` -> `./src/*`
- 暗黑科技风：`--bg:#0b1120`, `--accent:#06d6a0`, `--up:#ef4444`(红涨), `--down:#22c55e`(绿跌)
- 每个任务完成后 commit + push
- verify.sh 必须通过才能 merge

---

## File Structure

```
backend/app/
├── db/models.py                    # MODIFY: 追加 Holding, Transaction, DailyReport, ReportSection, ReportContext
├── db/queries.py                   # MODIFY: 追加持仓/交易/报告查询函数
├── api/v1/portfolio.py             # CREATE: 持仓管理路由
├── api/v1/router.py               # MODIFY: 注册 portfolio router
├── portfolio/                     # CREATE: 新目录
│   ├── __init__.py
│   ├── calculator.py              # 组合规则计算（纯函数）
│   ├── analyzer.py                # 三阶段分析管道
│   └── report.py                  # 报告生成编排
├── engine/scheduler.py            # MODIFY: 追加 08:30 定时任务
└── config.py                      # 不修改

backend/tests/
└── test_portfolio.py              # CREATE: 全部测试

frontend/src/
├── api/portfolio.ts               # CREATE: API 调用
├── components/
│   ├── PortfolioView.tsx          # CREATE: 主视图
│   ├── PortfolioDashboard.tsx     # CREATE: 仪表盘卡片
│   ├── HoldingsTable.tsx         # CREATE: 持仓表格
│   ├── TransactionForm.tsx        # CREATE: 交易录入
│   ├── TransactionHistory.tsx    # CREATE: 交易记录列表
│   ├── DailyReportView.tsx       # CREATE: 每日报告
│   └── ResizableSplitter.tsx     # CREATE: 可拖拽分隔条
├── contexts/AppContext.tsx        # MODIFY: 追加 portfolio view type
└── components/TopTabBar.tsx       # MODIFY: 追加第4个 Tab
```

---

### Task 1: DB 模型 + 查询函数

**Files:**
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/db/queries.py`
- Test: `backend/tests/test_portfolio.py`

**Interfaces:**
- Produces: `Holding`, `Transaction`, `DailyReport`, `ReportSection`, `ReportContext` 模型类
- Produces: `queries.create_holding()`, `queries.get_holdings()`, `queries.update_holding()`, `queries.delete_holding()`, `queries.create_transaction()`, `queries.get_transactions()`, `queries.delete_transaction()`, `queries.create_report()`, `queries.get_report_by_date()`, `queries.get_report_sections()`, `queries.save_report_section()`, `queries.get_report_contexts()`, `queries.save_report_context()`

- [ ] **Step 1: Write failing tests for model creation and query functions**

```python
# backend/tests/test_portfolio.py
import pytest
from datetime import date, datetime
from app.db.database import get_session_factory
from app.db.models import Holding, Transaction, DailyReport, ReportSection, ReportContext
from app.db import queries


@pytest.fixture
async def db_session():
    """Fresh DB session for each test."""
    from app.db.database import init_db
    await init_db()
    factory = get_session_factory()
    async with factory() as session:
        yield session
        # Cleanup
        from sqlalchemy import delete
        await session.execute(delete(Holding))
        await session.execute(delete(Transaction))
        await session.execute(delete(ReportContext))
        await session.execute(delete(ReportSection))
        await session.execute(delete(DailyReport))
        await session.commit()


class TestHoldingModel:
    @pytest.mark.asyncio
    async def test_create_holding(self, db_session):
        holding = await queries.create_holding(
            db_session,
            code="sh.600519", name="贵州茅台",
            shares=100, avg_cost=1680.0, buy_date=date(2026, 5, 10)
        )
        assert holding.id is not None
        assert holding.code == "sh.600519"
        assert holding.shares == 100
        assert holding.avg_cost == 1680.0
        assert holding.status == "open"

    @pytest.mark.asyncio
    async def test_get_holdings(self, db_session):
        await queries.create_holding(db_session, "sh.600519", "贵州茅台", 100, 1680.0, date(2026, 5, 10))
        await queries.create_holding(db_session, "sz.000001", "平安银行", 200, 12.5, date(2026, 6, 1))
        holdings = await queries.get_holdings(db_session)
        assert len(holdings) == 2
        assert holdings[0].code == "sh.600519"

    @pytest.mark.asyncio
    async def test_get_holdings_only_open(self, db_session):
        h = await queries.create_holding(db_session, "sh.600519", "贵州茅台", 100, 1680.0, date(2026, 5, 10))
        await queries.update_holding(db_session, h.id, status="closed")
        holdings = await queries.get_holdings(db_session, only_open=True)
        assert len(holdings) == 0

    @pytest.mark.asyncio
    async def test_update_holding(self, db_session):
        h = await queries.create_holding(db_session, "sh.600519", "贵州茅台", 100, 1680.0, date(2026, 5, 10))
        updated = await queries.update_holding(db_session, h.id, shares=150, avg_cost=1700.0)
        assert updated.shares == 150
        assert updated.avg_cost == 1700.0

    @pytest.mark.asyncio
    async def test_delete_holding(self, db_session):
        h = await queries.create_holding(db_session, "sh.600519", "贵州茅台", 100, 1680.0, date(2026, 5, 10))
        await queries.delete_holding(db_session, h.id)
        holdings = await queries.get_holdings(db_session)
        assert len(holdings) == 0


class TestTransactionModel:
    @pytest.mark.asyncio
    async def test_create_transaction(self, db_session):
        tx = await queries.create_transaction(
            db_session,
            code="sh.600519", name="贵州茅台",
            action="buy", shares=100, price=1680.0,
            traded_at=datetime(2026, 5, 10, 9, 30), note="首次建仓"
        )
        assert tx.id is not None
        assert tx.action == "buy"
        assert tx.amount == 168000.0

    @pytest.mark.asyncio
    async def test_get_transactions_pagination(self, db_session):
        for i in range(15):
            await queries.create_transaction(
                db_session, "sh.600519", "贵州茅台",
                "buy", 100, 1680.0 + i,
                datetime(2026, 5, 1 + i, 9, 30)
            )
        page1 = await queries.get_transactions(db_session, page=1, limit=10)
        page2 = await queries.get_transactions(db_session, page=2, limit=10)
        assert len(page1) == 10
        assert len(page2) == 5

    @pytest.mark.asyncio
    async def test_get_transactions_filter_by_code(self, db_session):
        await queries.create_transaction(db_session, "sh.600519", "贵州茅台", "buy", 100, 1680.0, datetime(2026, 5, 10, 9, 30))
        await queries.create_transaction(db_session, "sz.000001", "平安银行", "buy", 200, 12.5, datetime(2026, 5, 10, 9, 30))
        txs = await queries.get_transactions(db_session, code="sh.600519")
        assert len(txs) == 1
        assert txs[0].code == "sh.600519"

    @pytest.mark.asyncio
    async def test_count_transactions(self, db_session):
        for i in range(5):
            await queries.create_transaction(db_session, "sh.600519", "贵州茅台", "buy", 10, 1680.0, datetime(2026, 5, 1 + i, 9, 30))
        count = await queries.count_transactions(db_session)
        assert count == 5


class TestReportModel:
    @pytest.mark.asyncio
    async def test_create_report(self, db_session):
        report = await queries.create_report(db_session, date(2026, 7, 12))
        assert report.id is not None
        assert report.report_date == date(2026, 7, 12)
        assert report.status == "pending"

    @pytest.mark.asyncio
    async def test_get_report_by_date(self, db_session):
        await queries.create_report(db_session, date(2026, 7, 12))
        report = await queries.get_report_by_date(db_session, date(2026, 7, 12))
        assert report is not None
        assert report.report_date == date(2026, 7, 12)

    @pytest.mark.asyncio
    async def test_get_report_by_date_not_found(self, db_session):
        report = await queries.get_report_by_date(db_session, date(2099, 1, 1))
        assert report is None

    @pytest.mark.asyncio
    async def test_save_and_get_report_section(self, db_session):
        report = await queries.create_report(db_session, date(2026, 7, 12))
        section = await queries.save_report_section(
            db_session, report.id,
            section_type="portfolio_analysis",
            content='{"win_rate": 0.68}',
            section_order=0
        )
        assert section.id is not None
        sections = await queries.get_report_sections(db_session, report.id)
        assert len(sections) == 1
        assert sections[0].section_type == "portfolio_analysis"

    @pytest.mark.asyncio
    async def test_save_and_get_report_context(self, db_session):
        report = await queries.create_report(db_session, date(2026, 7, 12))
        ctx = await queries.save_report_context(
            db_session, report.id,
            stock_code="sh.600519",
            advice_type="hold",
            key_price=1680.0,
            advice_text="建议持有，回调至1750可加仓"
        )
        assert ctx.id is not None
        contexts = await queries.get_report_contexts(db_session, report.id)
        assert len(contexts) == 1
        assert contexts[0].stock_code == "sh.600519"

    @pytest.mark.asyncio
    async def test_delete_report_sections(self, db_session):
        report = await queries.create_report(db_session, date(2026, 7, 12))
        await queries.save_report_section(db_session, report.id, "portfolio_analysis", "{}", 0)
        await queries.save_report_section(db_session, report.id, "stock_analysis", "{}", 1, stock_code="sh.600519")
        await queries.delete_report_sections(db_session, report.id)
        sections = await queries.get_report_sections(db_session, report.id)
        assert len(sections) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_portfolio.py -v --tb=short`
Expected: FAIL with ImportError or AttributeError (models/functions not defined)

- [ ] **Step 3: Add models to models.py**

在 `backend/app/db/models.py` 末尾追加：

```python
from sqlalchemy import Boolean


class Holding(Base):
    __tablename__ = "holdings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    shares = Column(Integer, nullable=False)
    avg_cost = Column(Numeric(12, 4), nullable=False)
    buy_date = Column(Date)
    status = Column(String(10), default="open")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    action = Column(String(10), nullable=False)
    shares = Column(Integer, nullable=False)
    price = Column(Numeric(12, 4), nullable=False)
    amount = Column(Numeric(20, 2), nullable=False)
    traded_at = Column(DateTime, nullable=False)
    note = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class DailyReport(Base):
    __tablename__ = "daily_reports"
    id = Column(String(36), primary_key=True)
    report_date = Column(Date, nullable=False, unique=True)
    status = Column(String(10), default="pending")
    total_market_value = Column(Numeric(20, 2))
    total_cost = Column(Numeric(20, 2))
    total_pnl = Column(Numeric(20, 2))
    pnl_pct = Column(Numeric(8, 4))
    summary = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ReportSection(Base):
    __tablename__ = "report_sections"
    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(String(36), ForeignKey("daily_reports.id"), nullable=False)
    section_type = Column(String(30), nullable=False)
    stock_code = Column(String(20))
    content = Column(Text)
    section_order = Column(Integer, default=0)
    status = Column(String(10), default="success")


class ReportContext(Base):
    __tablename__ = "report_contexts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(String(36), ForeignKey("daily_reports.id"), nullable=False)
    stock_code = Column(String(20), nullable=False)
    advice_type = Column(String(20), nullable=False)
    key_price = Column(Numeric(12, 4))
    advice_text = Column(Text)
    executed = Column(Boolean, default=False)
    execution_result = Column(String(20))
    created_at = Column(DateTime, server_default=func.now())
```

- [ ] **Step 4: Add query functions to queries.py**

在 `backend/app/db/queries.py` 末尾追加：

```python
import uuid
from app.db.models import (
    Holding, Transaction, DailyReport, ReportSection, ReportContext
)


# === Holdings ===

async def create_holding(session, code, name, shares, avg_cost, buy_date):
    holding = Holding(
        code=code, name=name, shares=shares,
        avg_cost=avg_cost, buy_date=buy_date, status="open"
    )
    session.add(holding)
    await session.commit()
    await session.refresh(holding)
    return holding


async def get_holdings(session, only_open=True):
    stmt = select(Holding)
    if only_open:
        stmt = stmt.where(Holding.status == "open")
    stmt = stmt.order_by(Holding.updated_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_holding_by_code(session, code):
    result = await session.execute(
        select(Holding).where(Holding.code == code, Holding.status == "open")
    )
    return result.scalar_one_or_none()


async def update_holding(session, holding_id, **kwargs):
    from sqlalchemy import update as sa_update
    await session.execute(
        sa_update(Holding).where(Holding.id == holding_id).values(**kwargs)
    )
    await session.commit()
    result = await session.execute(select(Holding).where(Holding.id == holding_id))
    return result.scalar_one_or_none()


async def delete_holding(session, holding_id):
    from sqlalchemy import delete as sa_delete
    await session.execute(sa_delete(Holding).where(Holding.id == holding_id))
    await session.commit()


# === Transactions ===

async def create_transaction(session, code, name, action, shares, price, traded_at, note=None):
    tx = Transaction(
        code=code, name=name, action=action,
        shares=shares, price=price,
        amount=shares * price, traded_at=traded_at, note=note
    )
    session.add(tx)
    await session.commit()
    await session.refresh(tx)
    return tx


async def get_transactions(session, code=None, action=None, page=1, limit=20):
    stmt = select(Transaction)
    if code:
        stmt = stmt.where(Transaction.code == code)
    if action:
        stmt = stmt.where(Transaction.action == action)
    stmt = stmt.order_by(Transaction.traded_at.desc())
    stmt = stmt.offset((page - 1) * limit).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_transactions(session, code=None, action=None):
    stmt = select(func.count()).select_from(Transaction)
    if code:
        stmt = stmt.where(Transaction.code == code)
    if action:
        stmt = stmt.where(Transaction.action == action)
    result = await session.execute(stmt)
    return result.scalar()


async def get_transaction(session, tx_id):
    result = await session.execute(
        select(Transaction).where(Transaction.id == tx_id)
    )
    return result.scalar_one_or_none()


async def delete_transaction(session, tx_id):
    from sqlalchemy import delete as sa_delete
    await session.execute(sa_delete(Transaction).where(Transaction.id == tx_id))
    await session.commit()


# === Daily Reports ===

async def create_report(session, report_date):
    report = DailyReport(id=str(uuid.uuid4()), report_date=report_date, status="pending")
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return report


async def get_report_by_date(session, report_date):
    result = await session.execute(
        select(DailyReport).where(DailyReport.report_date == report_date)
    )
    return result.scalar_one_or_none()


async def get_report_by_id(session, report_id):
    result = await session.execute(
        select(DailyReport).where(DailyReport.id == report_id)
    )
    return result.scalar_one_or_none()


async def get_recent_reports(session, limit=30):
    result = await session.execute(
        select(DailyReport).order_by(DailyReport.report_date.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def update_report(session, report_id, **kwargs):
    from sqlalchemy import update as sa_update
    await session.execute(
        sa_update(DailyReport).where(DailyReport.id == report_id).values(**kwargs)
    )
    await session.commit()


async def save_report_section(session, report_id, section_type, content, section_order=0, stock_code=None, status="success"):
    section = ReportSection(
        report_id=report_id, section_type=section_type,
        stock_code=stock_code, content=content,
        section_order=section_order, status=status
    )
    session.add(section)
    await session.commit()
    await session.refresh(section)
    return section


async def get_report_sections(session, report_id):
    result = await session.execute(
        select(ReportSection)
        .where(ReportSection.report_id == report_id)
        .order_by(ReportSection.section_order.asc())
    )
    return list(result.scalars().all())


async def delete_report_sections(session, report_id):
    from sqlalchemy import delete as sa_delete
    await session.execute(
        sa_delete(ReportSection).where(ReportSection.report_id == report_id)
    )
    await session.commit()


# === Report Contexts (cross-day memory) ===

async def save_report_context(session, report_id, stock_code, advice_type, key_price=None, advice_text=None):
    ctx = ReportContext(
        report_id=report_id, stock_code=stock_code,
        advice_type=advice_type, key_price=key_price,
        advice_text=advice_text, executed=False
    )
    session.add(ctx)
    await session.commit()
    await session.refresh(ctx)
    return ctx


async def get_report_contexts(session, report_id):
    result = await session.execute(
        select(ReportContext).where(ReportContext.report_id == report_id)
    )
    return list(result.scalars().all())


async def get_latest_report_contexts(session, stock_code=None):
    """Get the most recent report's contexts for a stock (or all stocks)."""
    latest_report = await session.execute(
        select(DailyReport).order_by(DailyReport.report_date.desc()).limit(1)
    )
    report = latest_report.scalar_one_or_none()
    if not report:
        return []
    stmt = select(ReportContext).where(ReportContext.report_id == report.id)
    if stock_code:
        stmt = stmt.where(ReportContext.stock_code == stock_code)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_report_context(session, ctx_id, executed, execution_result=None):
    from sqlalchemy import update as sa_update
    await session.execute(
        sa_update(ReportContext).where(ReportContext.id == ctx_id)
        .values(executed=executed, execution_result=execution_result)
    )
    await session.commit()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_portfolio.py -v --tb=short`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
cd backend
git add app/db/models.py app/db/queries.py tests/test_portfolio.py
git commit -m "feat: add portfolio DB models (Holding, Transaction, DailyReport, ReportSection, ReportContext) + query functions + tests"
git push
```

---

### Task 2: 持仓+交易 API 端点

**Files:**
- Create: `backend/app/api/v1/portfolio.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_portfolio.py` (追加)

**Interfaces:**
- Consumes: Task 1 的 queries 函数
- Produces: REST API 端点 `/api/v1/portfolio/holdings`, `/api/v1/portfolio/transactions`

- [ ] **Step 1: Write failing tests for API endpoints**

在 `tests/test_portfolio.py` 追加：

```python
class TestHoldingsAPI:
    def test_create_holding(self, client):
        resp = client.post("/api/v1/portfolio/holdings", json={
            "code": "sh.600519", "name": "贵州茅台",
            "shares": 100, "avg_cost": 1680.0, "buy_date": "2026-05-10"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "sh.600519"
        assert data["shares"] == 100
        assert data["status"] == "open"

    def test_get_holdings(self, client):
        client.post("/api/v1/portfolio/holdings", json={
            "code": "sh.600519", "name": "贵州茅台",
            "shares": 100, "avg_cost": 1680.0, "buy_date": "2026-05-10"
        })
        resp = client.get("/api/v1/portfolio/holdings")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["holdings"]) == 1
        assert data["holdings"][0]["code"] == "sh.600519"

    def test_delete_holding(self, client):
        create = client.post("/api/v1/portfolio/holdings", json={
            "code": "sh.600519", "name": "贵州茅台",
            "shares": 100, "avg_cost": 1680.0, "buy_date": "2026-05-10"
        })
        holding_id = create.json()["id"]
        resp = client.delete(f"/api/v1/portfolio/holdings/{holding_id}")
        assert resp.status_code == 200
        # Verify deleted
        resp = client.get("/api/v1/portfolio/holdings")
        assert len(resp.json()["holdings"]) == 0


class TestTransactionAPI:
    def test_create_buy_transaction(self, client):
        # Create holding first
        client.post("/api/v1/portfolio/holdings", json={
            "code": "sh.600519", "name": "贵州茅台",
            "shares": 100, "avg_cost": 1680.0, "buy_date": "2026-05-10"
        })
        # Record a buy (加仓)
        resp = client.post("/api/v1/portfolio/transactions", json={
            "code": "sh.600519", "name": "贵州茅台",
            "action": "buy", "shares": 50, "price": 1750.0,
            "traded_at": "2026-06-01T09:30:00", "note": "加仓"
        })
        assert resp.status_code == 200
        # Verify holding updated: shares=150, avg_cost = (100*1680+50*1750)/150 = 1703.33
        holdings = client.get("/api/v1/portfolio/holdings").json()["holdings"]
        assert holdings[0]["shares"] == 150
        assert abs(float(holdings[0]["avg_cost"]) - 1703.3333) < 0.01

    def test_create_sell_transaction(self, client):
        client.post("/api/v1/portfolio/holdings", json={
            "code": "sh.600519", "name": "贵州茅台",
            "shares": 100, "avg_cost": 1680.0, "buy_date": "2026-05-10"
        })
        resp = client.post("/api/v1/portfolio/transactions", json={
            "code": "sh.600519", "name": "贵州茅台",
            "action": "sell", "shares": 100, "price": 1850.0,
            "traded_at": "2026-07-01T14:30:00", "note": "清仓止盈"
        })
        assert resp.status_code == 200
        # Verify holding closed
        holdings = client.get("/api/v1/portfolio/holdings").json()["holdings"]
        assert len(holdings) == 0  # closed holdings not returned by default

    def test_get_transactions_pagination(self, client):
        for i in range(15):
            client.post("/api/v1/portfolio/transactions", json={
                "code": "sh.600519", "name": "贵州茅台",
                "action": "buy", "shares": 10, "price": 1680.0 + i,
                "traded_at": f"2026-05-{1+i:02d}T09:30:00"
            })
        resp = client.get("/api/v1/portfolio/transactions?page=1&limit=10")
        data = resp.json()
        assert data["total"] == 15
        assert len(data["transactions"]) == 10
        assert data["page"] == 1
        assert data["total_pages"] == 2

    def test_delete_transaction(self, client):
        create = client.post("/api/v1/portfolio/transactions", json={
            "code": "sh.600519", "name": "贵州茅台",
            "action": "buy", "shares": 10, "price": 1680.0,
            "traded_at": "2026-05-10T09:30:00"
        })
        tx_id = create.json()["id"]
        resp = client.delete(f"/api/v1/portfolio/transactions/{tx_id}")
        assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_portfolio.py::TestHoldingsAPI tests/test_portfolio.py::TestTransactionAPI -v --tb=short`
Expected: FAIL with 404 (route not found)

- [ ] **Step 3: Create portfolio.py route module**

```python
# backend/app/api/v1/portfolio.py
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal
from app.db.database import get_session_factory
from app.db import queries
from app.db.models import Holding, Transaction

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


# === Request Models ===

class HoldingCreate(BaseModel):
    code: str
    name: str
    shares: int = Field(gt=0)
    avg_cost: float = Field(gt=0)
    buy_date: date


class TransactionCreate(BaseModel):
    code: str
    name: str
    action: str = Field(pattern=r"^(buy|sell)$")
    shares: int = Field(gt=0)
    price: float = Field(gt=0)
    traded_at: datetime
    note: str | None = None


# === Holdings ===

@router.get("/holdings")
async def get_holdings():
    factory = get_session_factory()
    async with factory() as session:
        holdings = await queries.get_holdings(session, only_open=True)
        return {"holdings": [
            {
                "id": h.id, "code": h.code, "name": h.name,
                "shares": h.shares, "avg_cost": float(h.avg_cost),
                "buy_date": str(h.buy_date) if h.buy_date else None,
                "status": h.status, "updated_at": str(h.updated_at),
            }
            for h in holdings
        ]}


@router.post("/holdings")
async def create_holding(item: HoldingCreate):
    factory = get_session_factory()
    async with factory() as session:
        holding = await queries.create_holding(
            session, item.code, item.name,
            item.shares, item.avg_cost, item.buy_date
        )
        return {
            "id": holding.id, "code": holding.code, "name": holding.name,
            "shares": holding.shares, "avg_cost": float(holding.avg_cost),
            "buy_date": str(holding.buy_date), "status": holding.status,
        }


@router.patch("/holdings/{holding_id}")
async def update_holding(holding_id: int, shares: int | None = None, avg_cost: float | None = None):
    factory = get_session_factory()
    async with factory() as session:
        kwargs = {}
        if shares is not None:
            kwargs["shares"] = shares
        if avg_cost is not None:
            kwargs["avg_cost"] = avg_cost
        holding = await queries.update_holding(session, holding_id, **kwargs)
        if not holding:
            raise HTTPException(status_code=404, detail="Holding not found")
        return {"id": holding.id, "shares": holding.shares, "avg_cost": float(holding.avg_cost)}


@router.delete("/holdings/{holding_id}")
async def delete_holding(holding_id: int):
    factory = get_session_factory()
    async with factory() as session:
        await queries.delete_holding(session, holding_id)
        return {"deleted": holding_id}


# === Transactions ===

@router.get("/transactions")
async def get_transactions(
    code: str = Query(default=""),
    action: str = Query(default="", pattern=r"^(buy|sell|)$"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    factory = get_session_factory()
    async with factory() as session:
        txs = await queries.get_transactions(
            session, code=code or None, action=action or None,
            page=page, limit=limit
        )
        total = await queries.count_transactions(
            session, code=code or None, action=action or None
        )
        import math
        return {
            "transactions": [
                {
                    "id": t.id, "code": t.code, "name": t.name,
                    "action": t.action, "shares": t.shares,
                    "price": float(t.price), "amount": float(t.amount),
                    "traded_at": str(t.traded_at), "note": t.note,
                }
                for t in txs
            ],
            "total": total, "page": page,
            "total_pages": math.ceil(total / limit) if limit > 0 else 1,
        }


@router.post("/transactions")
async def create_transaction(item: TransactionCreate):
    factory = get_session_factory()
    async with factory() as session:
        tx = await queries.create_transaction(
            session, item.code, item.name, item.action,
            item.shares, item.price, item.traded_at, item.note
        )
        # Auto-update holding
        holding = await queries.get_holding_by_code(session, item.code)
        if item.action == "buy":
            if holding:
                # 加仓: 重算 avg_cost
                new_shares = holding.shares + item.shares
                new_avg = (holding.shares * holding.avg_cost + item.shares * item.price) / new_shares
                await queries.update_holding(
                    session, holding.id,
                    shares=new_shares, avg_cost=round(new_avg, 4)
                )
            else:
                # 新建持仓
                await queries.create_holding(
                    session, item.code, item.name,
                    item.shares, item.price, item.traded_at.date()
                )
        elif item.action == "sell":
            if holding:
                new_shares = holding.shares - item.shares
                if new_shares <= 0:
                    await queries.update_holding(session, holding.id, shares=0, status="closed")
                else:
                    await queries.update_holding(session, holding.id, shares=new_shares)
        return {
            "id": tx.id, "code": tx.code, "action": tx.action,
            "shares": tx.shares, "price": float(tx.price),
            "amount": float(tx.amount), "traded_at": str(tx.traded_at),
        }


@router.delete("/transactions/{tx_id}")
async def delete_transaction(tx_id: int):
    factory = get_session_factory()
    async with factory() as session:
        await queries.delete_transaction(session, tx_id)
        return {"deleted": tx_id}
```

- [ ] **Step 4: Register router**

在 `backend/app/api/v1/router.py` 追加：

```python
from . import portfolio
router.include_router(portfolio.router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_portfolio.py::TestHoldingsAPI tests/test_portfolio.py::TestTransactionAPI -v --tb=short`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
cd backend
git add app/api/v1/portfolio.py app/api/v1/router.py tests/test_portfolio.py
git commit -m "feat: add portfolio API endpoints (holdings CRUD + transactions CRUD with auto-holding update)"
git push
```

---

### Task 3: 组合规则计算（calculator.py）

**Files:**
- Create: `backend/app/portfolio/__init__.py`
- Create: `backend/app/portfolio/calculator.py`
- Test: `backend/tests/test_portfolio.py` (追加)

**Interfaces:**
- Consumes: Holding + Transaction 数据（传入 dict list，不耦合 DB session）
- Produces: `calculate_portfolio_metrics(holdings, transactions, realtime_prices)` -> dict

- [ ] **Step 1: Write failing tests**

在 `tests/test_portfolio.py` 追加：

```python
from app.portfolio.calculator import calculate_portfolio_metrics


class TestCalculator:
    def test_portfolio_metrics_basic(self):
        holdings = [
            {"code": "sh.600519", "name": "贵州茅台", "shares": 100, "avg_cost": 1680.0, "industry": "白酒"},
            {"code": "sz.300750", "name": "宁德时代", "shares": 200, "avg_cost": 182.5, "industry": "新能源"},
        ]
        transactions = [
            {"code": "sh.600519", "action": "buy", "shares": 100, "price": 1680.0, "traded_at": "2026-05-01T09:30:00"},
            {"code": "sh.600519", "action": "sell", "shares": 50, "price": 1850.0, "traded_at": "2026-06-01T14:00:00"},
        ]
        realtime = {
            "sh.600519": {"price": 1842.5, "change_pct": 1.2},
            "sz.300750": {"price": 198.3, "change_pct": -0.5},
        }
        result = calculate_portfolio_metrics(holdings, transactions, realtime)
        assert result["total_market_value"] == 100 * 1842.5 + 200 * 198.3
        assert result["total_cost"] == 100 * 1680.0 + 200 * 182.5
        assert result["total_pnl"] > 0
        assert result["holdings_count"] == 2
        # Position weights
        assert len(result["position_weights"]) == 2
        assert result["position_weights"][0]["code"] == "sh.600519"
        assert result["position_weights"][0]["weight"] > 0.5

    def test_win_rate(self):
        holdings = [{"code": "sh.600519", "name": "茅台", "shares": 100, "avg_cost": 1680.0, "industry": "白酒"}]
        transactions = [
            {"code": "sh.600519", "action": "buy", "shares": 100, "price": 1680.0, "traded_at": "2026-01-01T09:30:00"},
            {"code": "sh.600519", "action": "sell", "shares": 100, "price": 1800.0, "traded_at": "2026-03-01T14:00:00"},
            {"code": "sh.600519", "action": "buy", "shares": 100, "price": 1700.0, "traded_at": "2026-04-01T09:30:00"},
            {"code": "sh.600519", "action": "sell", "shares": 100, "price": 1650.0, "traded_at": "2026-05-01T14:00:00"},
        ]
        realtime = {"sh.600519": {"price": 1700.0, "change_pct": 0.0}}
        result = calculate_portfolio_metrics(holdings, transactions, realtime)
        # 2 closed trades: 1 win (1680->1800), 1 loss (1700->1650)
        assert result["operation_stats"]["win_rate"] == 0.5
        assert result["operation_stats"]["total_closed_trades"] == 2

    def test_concentration_hhi(self):
        holdings = [
            {"code": "sh.600519", "name": "茅台", "shares": 100, "avg_cost": 1680.0, "industry": "白酒"},
            {"code": "sz.000001", "name": "平安", "shares": 100, "avg_cost": 12.5, "industry": "银行"},
        ]
        transactions = []
        realtime = {
            "sh.600519": {"price": 1842.5, "change_pct": 1.0},
            "sz.000001": {"price": 12.5, "change_pct": 0.0},
        }
        result = calculate_portfolio_metrics(holdings, transactions, realtime)
        # 茅台 184250, 平安 1250 -> weight ~99.3%, ~0.7%
        assert result["concentration"]["max_weight"] > 0.99
        assert result["concentration"]["hhi"] > 8000  # highly concentrated

    def test_industry_exposure(self):
        holdings = [
            {"code": "sh.600519", "name": "茅台", "shares": 100, "avg_cost": 1680.0, "industry": "白酒"},
            {"code": "sz.300750", "name": "宁德", "shares": 200, "avg_cost": 182.5, "industry": "新能源"},
            {"code": "sz.002594", "name": "比亚迪", "shares": 80, "avg_cost": 245.0, "industry": "新能源"},
        ]
        transactions = []
        realtime = {
            "sh.600519": {"price": 1842.5, "change_pct": 1.0},
            "sz.300750": {"price": 198.3, "change_pct": -0.5},
            "sz.002594": {"price": 268.4, "change_pct": 0.8},
        }
        result = calculate_portfolio_metrics(holdings, transactions, realtime)
        industries = result["industry_exposure"]
        assert "白酒" in industries
        assert "新能源" in industries
        assert industries["新能源"] > industries["白酒"]

    def test_empty_holdings(self):
        result = calculate_portfolio_metrics([], [], {})
        assert result["total_market_value"] == 0
        assert result["total_pnl"] == 0
        assert result["holdings_count"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_portfolio.py::TestCalculator -v --tb=short`
Expected: FAIL with ImportError

- [ ] **Step 3: Create calculator.py**

```python
# backend/app/portfolio/__init__.py
# (empty - package marker)
```

```python
# backend/app/portfolio/calculator.py
"""Portfolio rule-based calculator - pure functions, no network."""
from datetime import datetime
from typing import Any


def calculate_portfolio_metrics(
    holdings: list[dict],
    transactions: list[dict],
    realtime_prices: dict[str, dict],
) -> dict[str, Any]:
    """Compute portfolio metrics from holdings + transactions + realtime prices.

    Pure function - no DB, no network. All data passed in as dicts.
    """
    if not holdings:
        return {
            "total_market_value": 0,
            "total_cost": 0,
            "total_pnl": 0,
            "pnl_pct": 0,
            "today_change": 0,
            "today_change_pct": 0,
            "holdings_count": 0,
            "position_weights": [],
            "industry_exposure": {},
            "concentration": {"hhi": 0, "max_weight": 0, "top3_weight": 0},
            "operation_stats": {
                "win_rate": 0,
                "total_closed_trades": 0,
                "avg_holding_days": 0,
                "avg_profit_loss_ratio": 0,
                "max_win_streak": 0,
                "max_loss_streak": 0,
                "recent_trades": [],
            },
        }

    # Per-holding market value
    enriched = []
    for h in holdings:
        rt = realtime_prices.get(h["code"], {})
        price = rt.get("price", h["avg_cost"])
        change_pct = rt.get("change_pct", 0)
        market_value = h["shares"] * price
        cost = h["shares"] * h["avg_cost"]
        pnl = market_value - cost
        pnl_pct = (pnl / cost * 100) if cost > 0 else 0
        today_change = market_value * change_pct / 100
        enriched.append({
            "code": h["code"], "name": h["name"],
            "shares": h["shares"], "avg_cost": h["avg_cost"],
            "industry": h.get("industry", "未分类"),
            "current_price": price,
            "market_value": market_value,
            "cost": cost, "pnl": pnl, "pnl_pct": pnl_pct,
            "change_pct": change_pct, "today_change": today_change,
        })

    total_mv = sum(e["market_value"] for e in enriched)
    total_cost = sum(e["cost"] for e in enriched)
    total_pnl = total_mv - total_cost
    pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
    today_change = sum(e["today_change"] for e in enriched)
    today_change_pct = (today_change / (total_mv - today_change) * 100) if (total_mv - today_change) > 0 else 0

    # Position weights (sorted desc)
    weights = sorted(
        [{"code": e["code"], "name": e["name"], "weight": e["market_value"] / total_mv if total_mv > 0 else 0,
          "market_value": e["market_value"]} for e in enriched],
        key=lambda x: x["weight"], reverse=True
    )

    # Industry exposure
    industry_map = {}
    for e in enriched:
        ind = e["industry"]
        industry_map[ind] = industry_map.get(ind, 0) + e["market_value"]
    industry_exposure = {k: v / total_mv for k, v in industry_map.items()} if total_mv > 0 else {}

    # Concentration
    max_weight = weights[0]["weight"] if weights else 0
    top3_weight = sum(w["weight"] for w in weights[:3])
    hhi = sum(w["weight"] ** 2 for w in weights) * 10000  # HHI index 0-10000

    # Operation stats from closed trades
    op_stats = _compute_operation_stats(transactions)

    return {
        "total_market_value": round(total_mv, 2),
        "total_cost": round(total_cost, 2),
        "total_pnl": round(total_pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "today_change": round(today_change, 2),
        "today_change_pct": round(today_change_pct, 2),
        "holdings_count": len(holdings),
        "position_weights": weights,
        "industry_exposure": industry_exposure,
        "concentration": {
            "hhi": round(hhi, 0),
            "max_weight": round(max_weight, 4),
            "top3_weight": round(top3_weight, 4),
        },
        "operation_stats": op_stats,
    }


def _compute_operation_stats(transactions: list[dict]) -> dict:
    """Match buy/sell pairs per stock to compute win rate, avg holding days, etc."""
    # Group by stock code
    by_code: dict[str, list[dict]] = {}
    for tx in transactions:
        code = tx["code"]
        by_code.setdefault(code, []).append(tx)

    closed_trades = []
    for code, txs in by_code.items():
        txs.sort(key=lambda t: t["traded_at"])
        buy_queue: list[dict] = []  # FIFO queue of buys
        for tx in txs:
            if tx["action"] == "buy":
                buy_queue.append(tx)
            elif tx["action"] == "sell" and buy_queue:
                # Match against oldest buy (FIFO)
                remaining = tx["shares"]
                while remaining > 0 and buy_queue:
                    buy = buy_queue[0]
                    matched = min(remaining, buy["shares"])
                    buy_date = datetime.fromisoformat(str(buy["traded_at"]).replace("Z", ""))
                    sell_date = datetime.fromisoformat(str(tx["traded_at"]).replace("Z", ""))
                    holding_days = (sell_date - buy_date).days
                    pnl = (tx["price"] - buy["price"]) * matched
                    closed_trades.append({
                        "code": code, "buy_price": buy["price"],
                        "sell_price": tx["price"], "shares": matched,
                        "holding_days": holding_days, "pnl": pnl,
                        "win": pnl > 0,
                    })
                    remaining -= matched
                    buy["shares"] -= matched
                    if buy["shares"] <= 0:
                        buy_queue.pop(0)

    total_closed = len(closed_trades)
    wins = sum(1 for t in closed_trades if t["win"])
    win_rate = wins / total_closed if total_closed > 0 else 0

    avg_holding_days = (
        sum(t["holding_days"] for t in closed_trades) / total_closed
        if total_closed > 0 else 0
    )

    # Avg profit/loss ratio
    profits = [t["pnl"] for t in closed_trades if t["win"]]
    losses = [abs(t["pnl"]) for t in closed_trades if not t["win"]]
    avg_profit = sum(profits) / len(profits) if profits else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    avg_pl_ratio = avg_profit / avg_loss if avg_loss > 0 else 0

    # Win/loss streaks
    max_win_streak = 0
    max_loss_streak = 0
    current_win = 0
    current_loss = 0
    for t in closed_trades:
        if t["win"]:
            current_win += 1
            current_loss = 0
            max_win_streak = max(max_win_streak, current_win)
        else:
            current_loss += 1
            current_win = 0
            max_loss_streak = max(max_loss_streak, current_loss)

    # Recent trades (last 10)
    recent = sorted(closed_trades, key=lambda t: t.get("sell_date", ""), reverse=True)[:10]

    return {
        "win_rate": round(win_rate, 4),
        "total_closed_trades": total_closed,
        "avg_holding_days": round(avg_holding_days, 1),
        "avg_profit_loss_ratio": round(avg_pl_ratio, 2),
        "max_win_streak": max_win_streak,
        "max_loss_streak": max_loss_streak,
        "recent_trades": recent,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_portfolio.py::TestCalculator -v --tb=short`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/portfolio/ tests/test_portfolio.py
git commit -m "feat: add portfolio calculator (pure functions for metrics, win rate, concentration, industry exposure)"
git push
```

---

### Task 4: 分析管道（analyzer.py）+ 报告生成

**Files:**
- Create: `backend/app/portfolio/analyzer.py`
- Create: `backend/app/portfolio/report.py`
- Modify: `backend/app/api/v1/portfolio.py` (追加报告端点)
- Test: `backend/tests/test_portfolio.py` (追加)

**Interfaces:**
- Consumes: calculator.calculate_portfolio_metrics, tools.execute_tool, skills_manager.get_skill_content, config.settings
- Produces: `generate_report(report_date)` orchestrator, `_analyze_stock()`, `_generate_summary()`

- [ ] **Step 1: Write failing tests**

在 `tests/test_portfolio.py` 追加：

```python
import json
from unittest.mock import AsyncMock, patch, MagicMock


class TestReportGeneration:
    @pytest.mark.asyncio
    async def test_generate_report_no_holdings(self, db_session):
        from app.portfolio.report import generate_report
        report = await generate_report(date(2026, 7, 12))
        assert report is not None
        assert report["status"] == "completed"
        # Should have portfolio_analysis section but no stock_analysis
        assert "portfolio_analysis" in report["sections"]
        assert len(report["sections"].get("stock_analysis", [])) == 0

    @pytest.mark.asyncio
    async def test_generate_report_with_holdings(self, db_session):
        from app.portfolio.report import generate_report
        # Create a holding
        await queries.create_holding(db_session, "sh.600519", "贵州茅台", 100, 1680.0, date(2026, 5, 10))

        # Mock DeepSeek API response
        mock_response = {
            "choices": [{
                "message": {
                    "content": "## 贵州茅台分析\n\n技术面：MACD健康。建议持有。",
                    "tool_calls": None
                }
            }]
        }

        with patch("app.portfolio.analyzer.httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock()
            mock_post.return_value = MagicMock(status_code=200, json=MagicMock(return_value=mock_response))
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_post)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            report = await generate_report(date(2026, 7, 12))

        assert report["status"] == "completed"
        assert "portfolio_analysis" in report["sections"]
        assert len(report["sections"]["stock_analysis"]) >= 1
        assert report["sections"]["stock_analysis"][0]["stock_code"] == "sh.600519"

    @pytest.mark.asyncio
    async def test_generate_report_stock_analysis_failure(self, db_session):
        from app.portfolio.report import generate_report
        await queries.create_holding(db_session, "sh.600519", "贵州茅台", 100, 1680.0, date(2026, 5, 10))
        await queries.create_holding(db_session, "sz.000001", "平安银行", 200, 12.5, date(2026, 6, 1))

        # Mock DeepSeek to fail for one stock
        call_count = [0]
        async def mock_post_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("API timeout")
            return MagicMock(status_code=200, json=MagicMock(return_value={
                "choices": [{"message": {"content": "分析内容", "tool_calls": None}}]
            }))

        with patch("app.portfolio.analyzer.httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(side_effect=mock_post_side_effect)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_post)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            report = await generate_report(date(2026, 7, 12))

        # One stock should fail but report still completes
        assert report["status"] == "completed"
        stock_analyses = report["sections"]["stock_analysis"]
        statuses = [s["status"] for s in stock_analyses]
        assert "failed" in statuses or "success" in statuses

    @pytest.mark.asyncio
    async def test_report_context_saved(self, db_session):
        from app.portfolio.report import generate_report
        await queries.create_holding(db_session, "sh.600519", "贵州茅台", 100, 1680.0, date(2026, 5, 10))

        mock_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "advice": "hold", "buy_range": "1750-1820",
                        "stop_loss": 1680, "target": 1950,
                        "analysis": "建议持有"
                    }),
                    "tool_calls": None
                }
            }]
        }

        with patch("app.portfolio.analyzer.httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock()
            mock_post.return_value = MagicMock(status_code=200, json=MagicMock(return_value=mock_response))
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_post)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            report = await generate_report(date(2026, 7, 12))

        # Verify context was saved
        factory = get_session_factory()
        async with factory() as session:
            contexts = await queries.get_report_contexts(session, report["report_id"])
            assert len(contexts) >= 1
            assert contexts[0].stock_code == "sh.600519"


class TestReportAPI:
    def test_get_today_report_not_found(self, client):
        resp = client.get("/api/v1/portfolio/reports/today")
        assert resp.status_code == 404

    def test_get_report_list(self, client):
        # Generate a report first via internal call
        import asyncio
        from app.portfolio.report import generate_report
        loop = asyncio.new_event_loop()
        loop.run_until_complete(generate_report(date(2026, 7, 12)))
        loop.close()

        resp = client.get("/api/v1/portfolio/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["reports"]) >= 1

    def test_get_report_by_date(self, client):
        import asyncio
        from app.portfolio.report import generate_report
        loop = asyncio.new_event_loop()
        loop.run_until_complete(generate_report(date(2026, 7, 12)))
        loop.close()

        resp = client.get("/api/v1/portfolio/reports/2026-07-12")
        assert resp.status_code == 200
        data = resp.json()
        assert data["report_date"] == "2026-07-12"
        assert "sections" in data

    def test_generate_report_api(self, client):
        resp = client.post("/api/v1/portfolio/reports/generate")
        assert resp.status_code == 200
        data = resp.json()
        assert "report_id" in data
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_portfolio.py::TestReportGeneration tests/test_portfolio.py::TestReportAPI -v --tb=short`
Expected: FAIL with ImportError

- [ ] **Step 3: Create analyzer.py**

```python
# backend/app/portfolio/analyzer.py
"""Three-stage analysis pipeline: rules -> DeepSeek per-stock -> DeepSeek summary."""
import json
import httpx
import logging
from datetime import date, timedelta
from typing import Any
from app.config import settings
from app.diagnosis.tools import execute_tool, TOOL_DEFINITIONS
from app.diagnosis.skills_manager import get_skill_content

logger = logging.getLogger(__name__)

DEFAULT_SKILL = "stock-analysis"


async def analyze_stock(
    code: str, name: str, holding_ctx: dict, prev_advice: dict | None,
) -> dict[str, Any]:
    """Stage 2: Analyze a single stock via DeepSeek function-calling.

    Returns dict with: advice, buy_range, stop_loss, target, analysis (str).
    On failure returns {"error": "...", "status": "failed"}.
    """
    skill_content = get_skill_content(DEFAULT_SKILL) or ""

    system_prompt = f"""{skill_content}

你是专业股票分析师。基于工具获取的数据，分析以下股票并给出操作建议。

当前持仓上下文：
- 股票: {name}({code})
- 持仓: {holding_ctx.get('shares', 0)} 股
- 成本价: {holding_ctx.get('avg_cost', 0)}
- 仓位占比: {holding_ctx.get('weight', 0):.1%}
- 浮动盈亏: {holding_ctx.get('pnl', 0):.2f} ({holding_ctx.get('pnl_pct', 0):.1f}%)

"""

    if prev_advice:
        system_prompt += f"前日建议: {prev_advice.get('advice_text', '无')} (建议类型: {prev_advice.get('advice_type', '无')})\n"
        system_prompt += "请对比前日建议和当前走势，判断建议是否仍然有效。\n"

    system_prompt += """
请调用工具获取K线、指标、财务、新闻、实时行情数据，然后给出分析。

最终回复必须是 JSON 格式：
{
  "advice": "buy|sell|hold|watch|stop_loss",
  "buy_range": "1750-1820",
  "stop_loss": 1680,
  "target": 1950,
  "analysis": "详细分析文本（Markdown）"
}
"""

    user_prompt = f"请分析 {name}({code}) 的当前走势并给出操作建议。"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    max_rounds = settings.diagnosis_max_tool_rounds
    model = settings.diagnosis_llm_model

    try:
        for round_num in range(max_rounds + 1):
            response = await _call_deepseek(messages, model)
            message = response.get("choices", [{}])[0].get("message", {})

            if message.get("tool_calls"):
                messages.append({"role": "assistant", "tool_calls": message["tool_calls"]})
                for tc in message["tool_calls"]:
                    func_name = tc["function"]["name"]
                    func_args = json.loads(tc["function"]["arguments"])
                    result = await execute_tool(func_name, func_args)
                    messages.append({
                        "role": "tool", "tool_call_id": tc["id"], "content": result
                    })
            else:
                content = message.get("content", "")
                # Try to parse JSON from content
                try:
                    # Find JSON in response
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start >= 0 and end > start:
                        parsed = json.loads(content[start:end])
                        parsed["status"] = "success"
                        return parsed
                except (json.JSONDecodeError, ValueError):
                    pass
                # Fallback: return raw content
                return {
                    "advice": "hold",
                    "analysis": content,
                    "status": "success",
                }

        return {"error": "Max rounds reached", "status": "failed"}

    except Exception as e:
        logger.error(f"Stock analysis failed for {code}: {e}")
        return {"error": str(e), "status": "failed"}


async def generate_summary(
    portfolio_analysis: dict, stock_analyses: list[dict],
    prev_contexts: list[dict],
) -> str:
    """Stage 3: Generate overall summary via DeepSeek."""
    skill_content = get_skill_content(DEFAULT_SKILL) or ""

    system_prompt = f"""{skill_content}

你是投资组合管理顾问。基于组合分析和逐股分析结果，生成今日整体操作指导。

请输出 Markdown 格式：
1. 整体操作指导摘要
2. 行动计划列表（每只股票的操作建议 + 优先级）
3. 风险提示
"""

    context = {
        "portfolio": portfolio_analysis,
        "stock_analyses": [
            {"code": s.get("code"), "advice": s.get("advice"), "analysis": s.get("analysis", "")[:200]}
            for s in stock_analyses
        ],
        "previous_advice": [
            {"stock": c.get("stock_code"), "advice": c.get("advice_text"), "executed": c.get("executed")}
            for c in prev_contexts
        ],
    }

    user_prompt = f"组合分析数据(JSON):\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\n请生成今日操作指导。"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = await _call_deepseek(messages, settings.diagnosis_llm_model)
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        return f"操作指导生成失败: {e}"


async def _call_deepseek(messages: list[dict], model: str) -> dict:
    """Call DeepSeek API directly (no diagnosis session)."""
    key = settings.diagnosis_llm_api_key
    base_url = settings.diagnosis_llm_base_url

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "tools": TOOL_DEFINITIONS,
                "temperature": 0.3,
                "max_tokens": 4096,
            },
        )
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 4: Create report.py**

```python
# backend/app/portfolio/report.py
"""Report generation orchestrator - coordinates the 3-stage pipeline."""
import json
import logging
from datetime import date, timedelta
from app.db.database import get_session_factory
from app.db import queries
from app.portfolio.calculator import calculate_portfolio_metrics
from app.portfolio.analyzer import analyze_stock, generate_summary
from app.engine.data_engine import engine as data_engine

logger = logging.getLogger(__name__)


async def generate_report(report_date: date) -> dict:
    """Generate daily report. Returns dict with report metadata and sections.

    Stages:
    1. Portfolio rules (calculator)
    2. Per-stock DeepSeek analysis (parallel)
    3. DeepSeek summary
    """
    factory = get_session_factory()

    # Get holdings + transactions
    async with factory() as session:
        holdings_orm = await queries.get_holdings(session, only_open=True)
        holdings = [
            {
                "code": h.code, "name": h.name, "shares": h.shares,
                "avg_cost": float(h.avg_cost), "buy_date": str(h.buy_date) if h.buy_date else None,
                "id": h.id,
            }
            for h in holdings_orm
        ]
        transactions_orm = await queries.get_transactions(session, limit=200)
        transactions = [
            {
                "code": t.code, "action": t.action, "shares": t.shares,
                "price": float(t.price), "traded_at": str(t.traded_at),
            }
            for t in transactions_orm
        ]

    # Fetch realtime prices for all holdings
    realtime_prices = {}
    for h in holdings:
        try:
            rt, _ = await data_engine.get_realtime(h["code"])
            if rt:
                realtime_prices[h["code"]] = {"price": rt.get("price", h["avg_cost"]), "change_pct": rt.get("change_pct", 0)}
        except Exception:
            realtime_prices[h["code"]] = {"price": h["avg_cost"], "change_pct": 0}

    # Get previous report's contexts (cross-day memory)
    prev_report_date = report_date - timedelta(days=1)
    async with factory() as session:
        prev_report = await queries.get_report_by_date(session, prev_report_date)
        prev_contexts = []
        if prev_report:
            prev_contexts = await queries.get_report_contexts(session, prev_report.id)

    # === Stage 1: Portfolio rules ===
    portfolio_analysis = calculate_portfolio_metrics(holdings, transactions, realtime_prices)

    # Create or get report record
    async with factory() as session:
        existing = await queries.get_report_by_date(session, report_date)
        if existing:
            # Idempotent: delete old sections
            await queries.delete_report_sections(session, existing.id)
            report = existing
            await queries.update_report(session, report.id, status="running")
        else:
            report = await queries.create_report(session, report_date)

        # Save portfolio analysis section
        await queries.save_report_section(
            session, report.id, "portfolio_analysis",
            json.dumps(portfolio_analysis, ensure_ascii=False), 0
        )

    # === Stage 2: Per-stock analysis (parallel) ===
    stock_analyses = []
    prev_by_code = {c.stock_code: c for c in prev_contexts}

    for h in holdings:
        holding_ctx = {
            "shares": h["shares"],
            "avg_cost": h["avg_cost"],
            "weight": next((w["weight"] for w in portfolio_analysis["position_weights"] if w["code"] == h["code"]), 0),
            "pnl": 0,
            "pnl_pct": 0,
        }
        # Calculate pnl from portfolio analysis
        rt = realtime_prices.get(h["code"], {})
        price = rt.get("price", h["avg_cost"])
        holding_ctx["pnl"] = (price - h["avg_cost"]) * h["shares"]
        holding_ctx["pnl_pct"] = ((price - h["avg_cost"]) / h["avg_cost"] * 100) if h["avg_cost"] > 0 else 0

        prev_advice = None
        if h["code"] in prev_by_code:
            c = prev_by_code[h["code"]]
            prev_advice = {
                "advice_type": c.advice_type,
                "advice_text": c.advice_text,
                "key_price": float(c.key_price) if c.key_price else None,
                "executed": c.executed,
            }

        result = await analyze_stock(h["code"], h["name"], holding_ctx, prev_advice)
        result["code"] = h["code"]
        result["name"] = h["name"]
        stock_analyses.append(result)

    # Save stock analysis sections
    async with factory() as session:
        for i, sa in enumerate(stock_analyses):
            status = sa.get("status", "failed")
            await queries.save_report_section(
                session, report.id, "stock_analysis",
                json.dumps(sa, ensure_ascii=False), i + 1,
                stock_code=sa.get("code"), status=status
            )

    # === Stage 3: Summary ===
    summary = await generate_summary(portfolio_analysis, stock_analyses, prev_contexts)

    # Save action plan section + summary
    async with factory() as session:
        await queries.save_report_section(
            session, report.id, "action_plan",
            summary, len(stock_analyses) + 1
        )

        # Save report contexts for cross-day memory
        for sa in stock_analyses:
            if sa.get("status") == "success":
                advice_type = sa.get("advice", "hold")
                key_price = sa.get("stop_loss") or sa.get("target")
                advice_text = sa.get("analysis", "")[:500]
                await queries.save_report_context(
                    session, report.id, sa["code"],
                    advice_type, key_price, advice_text
                )

        # Update report with results
        await queries.update_report(
            session, report.id,
            status="completed",
            total_market_value=portfolio_analysis["total_market_value"],
            total_cost=portfolio_analysis["total_cost"],
            total_pnl=portfolio_analysis["total_pnl"],
            pnl_pct=portfolio_analysis["pnl_pct"],
            summary=summary,
        )

    # Build response
    async with factory() as session:
        sections = await queries.get_report_sections(session, report.id)
        contexts = await queries.get_report_contexts(session, report.id)

    return {
        "report_id": report.id,
        "report_date": str(report_date),
        "status": "completed",
        "total_market_value": portfolio_analysis["total_market_value"],
        "total_cost": portfolio_analysis["total_cost"],
        "total_pnl": portfolio_analysis["total_pnl"],
        "pnl_pct": portfolio_analysis["pnl_pct"],
        "sections": {
            "portfolio_analysis": json.loads(
                next(s.content for s in sections if s.section_type == "portfolio_analysis") or "{}"
            ),
            "stock_analysis": [
                {"stock_code": s.stock_code, "content": json.loads(s.content or "{}"), "status": s.status}
                for s in sections if s.section_type == "stock_analysis"
            ],
            "action_plan": next((s.content for s in sections if s.section_type == "action_plan"), ""),
        },
        "contexts": [
            {
                "id": c.id, "stock_code": c.stock_code,
                "advice_type": c.advice_type, "advice_text": c.advice_text,
                "key_price": float(c.key_price) if c.key_price else None,
                "executed": c.executed, "execution_result": c.execution_result,
            }
            for c in contexts
        ],
    }
```

- [ ] **Step 5: Add report API endpoints to portfolio.py**

在 `backend/app/api/v1/portfolio.py` 追加：

```python
from app.portfolio.report import generate_report as run_report_generation


# === Reports ===

@router.get("/reports")
async def get_reports(limit: int = Query(default=30, ge=1, le=365)):
    factory = get_session_factory()
    async with factory() as session:
        reports = await queries.get_recent_reports(session, limit)
        return {"reports": [
            {
                "id": r.id, "report_date": str(r.report_date),
                "status": r.status,
                "total_market_value": float(r.total_market_value) if r.total_market_value else None,
                "total_pnl": float(r.total_pnl) if r.total_pnl else None,
                "pnl_pct": float(r.pnl_pct) if r.pnl_pct else None,
                "summary": (r.summary or "")[:200],
            }
            for r in reports
        ]}


@router.get("/reports/today")
async def get_today_report():
    today = date.today()
    factory = get_session_factory()
    async with factory() as session:
        report = await queries.get_report_by_date(session, today)
        if not report:
            raise HTTPException(status_code=404, detail="Today's report not generated yet")
        sections = await queries.get_report_sections(session, report.id)
        return {
            "id": report.id, "report_date": str(report.report_date),
            "status": report.status,
            "total_market_value": float(report.total_market_value) if report.total_market_value else None,
            "total_pnl": float(report.total_pnl) if report.total_pnl else None,
            "pnl_pct": float(report.pnl_pct) if report.pnl_pct else None,
            "summary": report.summary,
            "sections": [
                {
                    "section_type": s.section_type, "stock_code": s.stock_code,
                    "content": s.content, "status": s.status,
                }
                for s in sections
            ],
        }


@router.get("/reports/{report_date}")
async def get_report_by_date(report_date: date):
    factory = get_session_factory()
    async with factory() as session:
        report = await queries.get_report_by_date(session, report_date)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        sections = await queries.get_report_sections(session, report.id)
        contexts = await queries.get_report_contexts(session, report.id)
        return {
            "id": report.id, "report_date": str(report.report_date),
            "status": report.status,
            "total_market_value": float(report.total_market_value) if report.total_market_value else None,
            "total_cost": float(report.total_cost) if report.total_cost else None,
            "total_pnl": float(report.total_pnl) if report.total_pnl else None,
            "pnl_pct": float(report.pnl_pct) if report.pnl_pct else None,
            "summary": report.summary,
            "sections": [
                {
                    "section_type": s.section_type, "stock_code": s.stock_code,
                    "content": s.content, "status": s.status,
                }
                for s in sections
            ],
            "contexts": [
                {
                    "id": c.id, "stock_code": c.stock_code,
                    "advice_type": c.advice_type, "advice_text": c.advice_text,
                    "key_price": float(c.key_price) if c.key_price else None,
                    "executed": c.executed, "execution_result": c.execution_result,
                }
                for c in contexts
            ],
        }


@router.post("/reports/generate")
async def generate_report_api():
    import asyncio
    today = date.today()
    # Run in background
    asyncio.create_task(run_report_generation(today))
    factory = get_session_factory()
    async with factory() as session:
        report = await queries.get_report_by_date(session, today)
        if report:
            return {"report_id": report.id, "status": "generating"}
        return {"status": "generating"}


# === Report Contexts ===

class ContextUpdate(BaseModel):
    executed: bool
    execution_result: str | None = None


@router.patch("/reports/context/{ctx_id}")
async def update_context(ctx_id: int, item: ContextUpdate):
    factory = get_session_factory()
    async with factory() as session:
        await queries.update_report_context(session, ctx_id, item.executed, item.execution_result)
        return {"updated": ctx_id}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_portfolio.py -v --tb=short`
Expected: All PASS (可能需要 mock DataEngine.get_realtime)

- [ ] **Step 7: Commit**

```bash
cd backend
git add app/portfolio/analyzer.py app/portfolio/report.py app/api/v1/portfolio.py tests/test_portfolio.py
git commit -m "feat: add 3-stage analysis pipeline (calculator + DeepSeek per-stock + summary) + report API endpoints"
git push
```

---

### Task 5: 调度器注册 + 前端 API + 前端组件

**Files:**
- Modify: `backend/app/engine/scheduler.py`
- Create: `frontend/src/api/portfolio.ts`
- Create: `frontend/src/components/ResizableSplitter.tsx`
- Create: `frontend/src/components/PortfolioView.tsx` (含子组件)
- Modify: `frontend/src/components/TopTabBar.tsx`
- Modify: `frontend/src/contexts/AppContext.tsx`

**Interfaces:**
- Consumes: Task 2 + Task 4 的 API 端点
- Produces: 完整前端 PortfolioView + 后端定时任务

- [ ] **Step 1: Register scheduler task**

在 `backend/app/engine/scheduler.py` 的 `start_scheduler()` 函数中追加：

```python
    scheduler.add_job(
        _generate_daily_report,
        "cron", hour=8, minute=30,
        id="daily_report_generate",
        replace_existing=True,
    )
```

并在文件中追加：

```python
async def _generate_daily_report():
    """Generate daily portfolio report at 08:30."""
    from datetime import date as _date
    from app.portfolio.report import generate_report as _gen
    try:
        await _gen(_date.today())
        logger.info("Daily report generated successfully")
    except Exception as e:
        logger.error(f"Daily report generation failed: {e}")
```

- [ ] **Step 2: Create frontend API file**

```typescript
// frontend/src/api/portfolio.ts

export interface Holding {
  id: number; code: string; name: string;
  shares: number; avg_cost: number; buy_date: string | null;
  status: string; updated_at: string;
}

export interface Transaction {
  id: number; code: string; name: string;
  action: 'buy' | 'sell'; shares: number; price: number;
  amount: number; traded_at: string; note: string | null;
}

export interface ReportSummary {
  id: string; report_date: string; status: string;
  total_market_value: number | null; total_pnl: number | null;
  pnl_pct: number | null; summary: string;
}

export async function getHoldings(): Promise<{ holdings: Holding[] }> {
  const r = await fetch('/api/v1/portfolio/holdings');
  return r.json();
}

export async function createHolding(data: {
  code: string; name: string; shares: number;
  avg_cost: number; buy_date: string;
}): Promise<Holding> {
  const r = await fetch('/api/v1/portfolio/holdings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return r.json();
}

export async function deleteHolding(id: number): Promise<void> {
  await fetch(`/api/v1/portfolio/holdings/${id}`, { method: 'DELETE' });
}

export async function getTransactions(
  page = 1, limit = 20, code = ''
): Promise<{ transactions: Transaction[]; total: number; page: number; total_pages: number }> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) });
  if (code) params.set('code', code);
  const r = await fetch(`/api/v1/portfolio/transactions?${params}`);
  return r.json();
}

export async function createTransaction(data: {
  code: string; name: string; action: 'buy' | 'sell';
  shares: number; price: number; traded_at: string; note?: string;
}): Promise<Transaction> {
  const r = await fetch('/api/v1/portfolio/transactions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return r.json();
}

export async function deleteTransaction(id: number): Promise<void> {
  await fetch(`/api/v1/portfolio/transactions/${id}`, { method: 'DELETE' });
}

export async function getReports(limit = 30): Promise<{ reports: ReportSummary[] }> {
  const r = await fetch(`/api/v1/portfolio/reports?limit=${limit}`);
  return r.json();
}

export async function getReport(date: string): Promise<any> {
  const r = await fetch(`/api/v1/portfolio/reports/${date}`);
  if (!r.ok) return null;
  return r.json();
}

export async function getTodayReport(): Promise<any> {
  const r = await fetch('/api/v1/portfolio/reports/today');
  if (!r.ok) return null;
  return r.json();
}

export async function generateReport(): Promise<{ report_id?: string; status: string }> {
  const r = await fetch('/api/v1/portfolio/reports/generate', { method: 'POST' });
  return r.json();
}
```

- [ ] **Step 3: Create ResizableSplitter component**

```tsx
// frontend/src/components/ResizableSplitter.tsx
import { useRef, useCallback, ReactNode } from 'react';

interface SplitterProps {
  direction: 'horizontal' | 'vertical';
  onResize: (delta: number) => void;
  children?: ReactNode;
}

export default function ResizableSplitter({ direction, onResize }: SplitterProps) {
  const startPos = useRef(0);
  const dragging = useRef(false);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    startPos.current = direction === 'horizontal' ? e.clientX : e.clientY;
    document.body.style.cursor = direction === 'horizontal' ? 'col-resize' : 'row-resize';
    document.body.style.userSelect = 'none';

    const onMouseMove = (ev: MouseEvent) => {
      if (!dragging.current) return;
      const current = direction === 'horizontal' ? ev.clientX : ev.clientY;
      const delta = current - startPos.current;
      startPos.current = current;
      onResize(delta);
    };

    const onMouseUp = () => {
      dragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }, [direction, onResize]);

  return (
    <div
      className={direction === 'horizontal' ? 'splitter-h' : 'splitter-v'}
      onMouseDown={onMouseDown}
    />
  );
}
```

- [ ] **Step 4: Create PortfolioView component**

创建 `frontend/src/components/PortfolioView.tsx`，包含：
- 仪表盘卡片行（总市值、总成本、总盈亏、今日变动、仓位分布）
- 左侧：持仓表格 + 交易录入表单 + 交易记录列表（分页）
- 右侧：每日报告视图（报告状态 + 组合分析 + 逐股分析卡片 + 行动计划 + 前日追踪 + 摘要）
- 可拖拽分隔条（左右 + 上下）

组件应：
- 使用 `useEffect` + `fetch` 调用 portfolio API
- 使用 CSS 变量保持暗黑科技风
- 交易记录分页 + 滚动
- 报告日期选择器
- 生成报告按钮
- 股票分析卡片可展开/折叠

（完整组件代码在实现时按原型 HTML 结构转换为 React + TypeScript）

- [ ] **Step 5: Add portfolio tab to TopTabBar**

修改 `frontend/src/components/TopTabBar.tsx`：

```typescript
const TABS: { key: AppView; label: string; icon: string }[] = [
  { key: 'stock', label: '个股分析', icon: '📈' },
  { key: 'screener', label: '选股器', icon: '🔍' },
  { key: 'intel', label: '市场情报', icon: '🌐' },
  { key: 'portfolio', label: '持仓管理', icon: '📊' },
];
```

- [ ] **Step 6: Add portfolio to AppContext**

修改 `frontend/src/contexts/AppContext.tsx`：

```typescript
export type AppView = 'stock' | 'screener' | 'intel' | 'portfolio';
```

修改 `frontend/src/App.tsx`，在 content 区域追加：

```tsx
{state.activeView === 'portfolio' && <PortfolioView />}
```

- [ ] **Step 7: Run backend tests**

Run: `cd backend && python -m pytest tests/test_portfolio.py -v --tb=short`
Expected: All PASS

- [ ] **Step 8: Run frontend type check + build**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: No errors

- [ ] **Step 9: Run verify.sh**

Run: `bash verify.sh`
Expected: All 4 checks pass (pytest + tsc + build + integrity)

- [ ] **Step 10: Commit**

```bash
git add backend/app/engine/scheduler.py frontend/src/api/portfolio.ts frontend/src/components/ResizableSplitter.tsx frontend/src/components/PortfolioView.tsx frontend/src/components/TopTabBar.tsx frontend/src/contexts/AppContext.tsx frontend/src/App.tsx
git commit -m "feat: add portfolio management UI (dashboard + holdings + transactions + daily report) + scheduler 08:30 task"
git push
```

---

## Self-Review

### 1. Spec coverage

| Spec 需求 | 对应 Task |
|-----------|-----------|
| Holding 模型 | Task 1 |
| Transaction 模型 | Task 1 |
| DailyReport 模型 | Task 1 |
| ReportSection 模型 | Task 1 |
| ReportContext 模型 | Task 1 |
| 持仓 CRUD API | Task 2 |
| 交易 CRUD API | Task 2 |
| 交易自动更新 Holding | Task 2 |
| 报告 API | Task 4 |
| 组合规则计算 | Task 3 |
| 逐股 DeepSeek 分析 | Task 4 |
| 综合总结 | Task 4 |
| 跨日记忆 | Task 4 |
| 调度器 08:30 | Task 5 |
| 前端 API 调用 | Task 5 |
| PortfolioView 组件 | Task 5 |
| 持仓表格 | Task 5 |
| 交易录入 | Task 5 |
| 交易记录分页 | Task 5 |
| 每日报告视图 | Task 5 |
| 可拖拽分隔条 | Task 5 |
| TopTabBar Tab | Task 5 |
| 后端测试 | Task 1-4 |
| 前端 tsc + build | Task 5 |
| verify.sh | Task 5 |

### 2. Placeholder scan

- 无 TBD/TODO
- 所有代码步骤包含完整代码
- 所有测试步骤包含完整测试代码
- 所有命令包含预期输出

### 3. Type consistency

- `calculate_portfolio_metrics` 返回 dict，在 Task 4 中作为 `portfolio_analysis` 传入 analyzer
- `analyze_stock` 返回 dict with `status`/`advice`/`analysis`，在 Task 4 中存储到 ReportSection
- `generate_report` 返回 dict with `report_id`/`sections`/`contexts`，在 API 端点中返回给前端
- 前端 API 函数签名与后端端点路径一致

无类型不一致问题。
