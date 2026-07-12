import pytest
import pytest_asyncio
import asyncio
from datetime import date, datetime
from sqlalchemy import delete as sa_delete
from app.db.database import get_session_factory
from app.db.models import Holding, Transaction, DailyReport, ReportSection, ReportContext
from app.db import queries


@pytest.fixture(autouse=True)
def _clean_portfolio_tables():
    """Clean portfolio tables before each test to prevent data leakage between tests."""
    async def _clean():
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(sa_delete(Holding))
            await session.execute(sa_delete(Transaction))
            await session.commit()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_clean())
    finally:
        loop.close()
    yield


@pytest_asyncio.fixture
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
