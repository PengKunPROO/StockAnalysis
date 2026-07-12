"""Tests for tonghuashun fuyao client extensions - parse correctness + degradation + smoke."""
import asyncio
import pytest


def _src():
    from app.datasources.tonghuashun import TonghuashunSource
    return TonghuashunSource()


def _patch_get(monkeypatch, response):
    """Patch _get to return `response` (a dict). For list-returning APIs data is a dict with item/list."""
    async def fake_get(self, path, params=None):
        return response
    monkeypatch.setattr("app.datasources.tonghuashun.TonghuashunSource._get", fake_get)


def _patch_raise(monkeypatch, exc=Exception("network down")):
    async def fake_get(self, path, params=None):
        raise exc
    monkeypatch.setattr("app.datasources.tonghuashun.TonghuashunSource._get", fake_get)


# ---------- parse correctness ----------
def test_market_snapshot_parse(monkeypatch):
    _patch_get(monkeypatch, {"item": [
        {"thscode": "600519.SH", "name": "贵州茅台", "last_price": 1700.0,
         "price_change_ratio_pct": 1.74, "volume": 12345, "turnover": 999.0,
         "open_price": 1680, "high_price": 1710, "low_price": 1675, "prev_price": 1690},
    ]})
    out = asyncio.run(_src().fetch_market_snapshot())
    assert len(out) == 1
    q = out[0]
    assert q["code"] == "sh.600519"
    assert q["name"] == "贵州茅台"
    assert q["price"] == 1700.0
    assert q["change_pct"] == 1.74
    assert q["amount"] == 999.0


def test_limit_up_pool_parse(monkeypatch):
    _patch_get(monkeypatch, {"item": [
        {"thscode": "600519.SH", "name": "贵州茅台", "last_price": 1700,
         "price_change_ratio_pct": 10.0, "limit_up_time": "093000",
         "limit_up_reason": "业绩", "continue_day_cnt": 3, "seal_money": 5e8},
    ]})
    out = asyncio.run(_src().fetch_limit_up_pool("20260708"))
    assert out[0]["code"] == "sh.600519"
    assert out[0]["consecutive_days"] == 3
    assert out[0]["seal_amount"] == 5e8
    assert out[0]["reason"] == "业绩"


def test_dragon_tiger_parse(monkeypatch):
    _patch_get(monkeypatch, {"stock_items": [
        {"thscode": "600519.SH", "name": "贵州茅台", "explain": "日涨幅偏离",
         "price_change_ratio_pct": 9.5, "net_buy": 1.2e8},
    ]})
    out = asyncio.run(_src().fetch_dragon_tiger("20260707"))
    assert out[0]["code"] == "sh.600519"
    assert out[0]["net_buy"] == 1.2e8


def test_anomaly_list_parse(monkeypatch):
    _patch_get(monkeypatch, {"item": [
        {"thscode": "600519.SH", "stock_name": "贵州茅台",
         "analysis_content": "涨停", "keyword_list": ["白酒"], "tag_name": "涨停"},
    ]})
    out = asyncio.run(_src().fetch_anomaly_list())
    assert out[0]["name"] == "贵州茅台"
    assert out[0]["tag"] == "涨停"
    assert out[0]["keywords"] == ["白酒"]


def test_ticker_list_parse(monkeypatch):
    _patch_get(monkeypatch, {"item": [
        {"thscode": "600519.SH", "name": "贵州茅台", "exchange": "SH"},
    ]})
    out = asyncio.run(_src().fetch_ticker_list())
    assert out[0]["code"] == "sh.600519"
    assert out[0]["name"] == "贵州茅台"


def test_index_snapshot_parse(monkeypatch):
    _patch_get(monkeypatch, {"item": [
        {"thscode": "000001.SH", "last_price": 3200, "price_change_ratio_pct": 0.5,
         "volume": 0, "turnover": 0, "open_price": 3190, "high_price": 3210, "low_price": 3185, "prev_price": 3184},
    ]})
    out = asyncio.run(_src().fetch_index_snapshot(["000001.SH"]))
    assert out[0]["price"] == 3200
    assert out[0]["change_pct"] == 0.5


# ---------- degradation: never raises ----------
@pytest.mark.parametrize("method,args", [
    ("fetch_market_snapshot", ()),
    ("fetch_limit_up_pool", ()),
    ("fetch_limit_up_ladder", ()),
    ("fetch_dragon_tiger", ()),
    ("fetch_anomaly_list", ()),
    ("fetch_anomaly_stock", (["sh.600519"],)),
    ("fetch_hot_stock", ()),
    ("fetch_ticker_list", ()),
    ("fetch_index_snapshot", (["000001.SH"],)),
])
def test_degrade_on_network_error(monkeypatch, method, args):
    _patch_raise(monkeypatch)
    src = _src()
    out = asyncio.run(getattr(src, method)(*args))
    assert out == [] or out is None


# ---------- smoke: real API (skip if no key) ----------
def _has_key():
    try:
        return bool(_src()._get_key())
    except Exception:
        return False


@pytest.mark.skipif(not _has_key(), reason="no fuyao api key")
def test_smoke_market_snapshot():
    out = asyncio.run(_src().fetch_market_snapshot(limit=5))
    assert isinstance(out, list)


@pytest.mark.skipif(not _has_key(), reason="no fuyao api key")
def test_smoke_index_snapshot():
    out = asyncio.run(_src().fetch_index_snapshot(["000001.SH"]))
    assert isinstance(out, list)


@pytest.mark.skipif(not _has_key(), reason="no fuyao api key")
def test_smoke_anomaly_list():
    out = asyncio.run(_src().fetch_anomaly_list())
    assert isinstance(out, list)


# ---------- kline pagination dedup ----------
def test_kline_pagination_dedup(monkeypatch):
    """fuyao API ignores offset param, returns same items every call.
    fetch_kline must deduplicate and terminate, not infinite-loop."""
    call_count = [0]

    async def fake_get(self, path, params=None):
        call_count[0] += 1
        if call_count[0] > 3:
            # Safety: should never reach here if dedup works
            return {"item": []}
        return {"item": [
            {"date_ms": 1700000000000, "open_price": 10, "high_price": 11,
             "low_price": 9, "close_price": 10.5, "volume": 1000, "turnover": 10000},
            {"date_ms": 1700086400000, "open_price": 10.5, "high_price": 11.5,
             "low_price": 10, "close_price": 11, "volume": 2000, "turnover": 22000},
        ]}

    monkeypatch.setattr("app.datasources.tonghuashun.TonghuashunSource._get", fake_get)
    src = _src()
    bars = asyncio.run(src.fetch_kline("sh.600519", "daily", "2023-01-01", "2023-12-31"))
    assert len(bars) == 2  # deduped, not duplicated
    assert call_count[0] == 2  # second call returned only dupes -> broke loop
