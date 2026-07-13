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


def test_klines_fetch_first_then_cache_fallback(monkeypatch):
    """fetch-first策略: 总是先请求真实数据源, 成功则更新缓存; 失败才回退到缓存。"""
    import asyncio
    from datetime import date, timedelta
    from app.engine.data_engine import engine
    from app.db.database import get_session_factory
    from app.db import queries
    from app.datasources.tonghuashun import TonghuashunSource

    code = "sh.999999"
    today = date.today()
    bars = [{"trade_date": today, "open": 100, "high": 101, "low": 99,
             "close": 100.5, "volume": 1000, "amount": 1e6}]

    async def setup():
        factory = get_session_factory()
        async with factory() as s:
            await queries.upsert_daily_klines(s, code, bars)
            await s.commit()
    asyncio.run(setup())

    # Scenario 1: source returns data -> should use it (not cache)
    called = {"n": 0}
    async def fake_fetch_ok(self, *a, **k):
        called["n"] += 1
        from app.datasources.base import KlineBar
        return [KlineBar(date=today.isoformat(), open=200, high=201, low=199, close=200.5, volume=2000, amount=2e6)]
    monkeypatch.setattr(TonghuashunSource, "fetch_kline", fake_fetch_ok)
    end = today.isoformat()
    start = (today - timedelta(days=365)).isoformat()
    data, _ = asyncio.run(engine.get_klines(code, "daily", start, end))
    assert called["n"] >= 1, "should always try network first (fetch-first)"
    assert data[-1]["close"] == 200.5, "should use fresh data, not stale cache"

    # Scenario 2: source fails -> should fall back to cache
    called2 = {"n": 0}
    async def fake_fetch_fail(self, *a, **k):
        called2["n"] += 1
        return []
    monkeypatch.setattr(TonghuashunSource, "fetch_kline", fake_fetch_fail)
    data2, warn2 = asyncio.run(engine.get_klines(code, "daily", start, end))
    assert called2["n"] >= 1, "should have tried network"
    assert len(data2) >= 1, "should fall back to cache"
    assert warn2 is not None, "should warn about using cache"
