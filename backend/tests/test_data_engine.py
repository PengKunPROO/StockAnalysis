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
