def test_tonghuashun_source_import():
    from app.datasources.tonghuashun import TonghuashunSource
    t = TonghuashunSource()
    assert t.name == "tonghuashun"
    assert "a_share" in t.markets


def test_tonghuashun_code_conversion():
    from app.datasources.tonghuashun import TonghuashunSource
    t = TonghuashunSource()
    assert t._to_ths_code("sh.600519") == "600519.SH"
    assert t._to_our_code("600519.SH") == "sh.600519"


def test_tonghuashun_health_check():
    from app.datasources.tonghuashun import TonghuashunSource
    assert isinstance(TonghuashunSource().health_check(), bool)


def test_sample_source():
    import asyncio
    from app.datasources.sample import SampleSource
    s = SampleSource()
    stocks = asyncio.run(s.search_stocks("600519"))
    assert len(stocks) > 0
    assert stocks[0].code == "sh.600519"


def test_registry_order():
    from app.datasources import get_source_for_market
    primary = get_source_for_market("a_share")
    assert primary.name == "tonghuashun"
