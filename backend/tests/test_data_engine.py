def test_market_from_code():
    from app.engine.data_engine import DataEngine
    e = DataEngine()
    assert e._market_from_code("sh.600519") == "a_share"
    assert e._market_from_code("sz.000001") == "a_share"
    assert e._market_from_code("us.AAPL") == "us"


def test_engine_health():
    import asyncio
    from app.engine.data_engine import engine
    result = asyncio.run(engine.health())
    assert "status" in result
    assert "datasources" in result
    assert "database" in result
    assert "tonghuashun" in result["datasources"]


def test_klines_recent_cache_skips_network(monkeypatch):
    """bug1 兜底: 缓存覆盖近期(end-7天)时直接返回, 不走慢网络。"""
    import asyncio
    from datetime import date, timedelta
    from app.engine.data_engine import engine
    from app.db.database import get_session_factory
    from app.db import queries

    code = "sh.999999"  # 测试专用, 不与真实股票冲突
    today = date.today()
    bars = [{"trade_date": today, "open": 100, "high": 101, "low": 99,
             "close": 100.5, "volume": 1000, "amount": 1e6}]

    async def setup():
        factory = get_session_factory()
        async with factory() as s:
            await queries.upsert_daily_klines(s, code, bars)
            await s.commit()
    asyncio.run(setup())

    called = {"n": 0}

    async def fake_fetch(self, *a, **k):
        called["n"] += 1
        return []
    from app.datasources.tonghuashun import TonghuashunSource
    monkeypatch.setattr(TonghuashunSource, "fetch_kline", fake_fetch)

    end = today.isoformat()
    start = (today - timedelta(days=365)).isoformat()
    data, _ = asyncio.run(engine.get_klines(code, "daily", start, end))
    assert called["n"] == 0, "should not hit network when recent cache exists"
    assert len(data) >= 1
