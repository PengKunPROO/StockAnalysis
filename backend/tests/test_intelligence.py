"""Tests for 市场情报 intelligence API - structure + graceful degradation."""
import pytest


def _assert_200_or_degraded(r):
    """Endpoint must be 200 (with data or warning), never 500."""
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"


def test_overview_structure(client):
    r = client.get("/api/v1/intelligence/overview")
    _assert_200_or_degraded(r)
    data = r.json()
    for key in ("indices", "breadth", "red_ratio", "limit_up_count", "board_buckets", "sentiment"):
        assert key in data, f"Missing: {key}"
    assert "fear_greed" in data["sentiment"]
    assert "fear_greed_label" in data["sentiment"]
    assert 0 <= data["sentiment"]["fear_greed"] <= 100
    assert 0 <= data["red_ratio"] <= 100


def test_limit_up_structure(client):
    r = client.get("/api/v1/intelligence/limit-up")
    _assert_200_or_degraded(r)
    data = r.json()
    assert "stocks" in data
    if data["stocks"]:
        first = data["stocks"][0]
        for key in ("code", "name", "consecutive_days"):
            assert key in first


def test_fund_flow_industry(client):
    r = client.get("/api/v1/intelligence/fund-flow?scope=industry")
    _assert_200_or_degraded(r)
    data = r.json()
    assert "sectors" in data or "warning" in data


def test_fund_flow_north(client):
    r = client.get("/api/v1/intelligence/fund-flow?scope=north")
    _assert_200_or_degraded(r)
    data = r.json()
    assert "north" in data or "warning" in data


def test_fund_flow_invalid_scope_422(client):
    r = client.get("/api/v1/intelligence/fund-flow?scope=invalid")
    assert r.status_code == 422


def test_sectors_structure(client):
    r = client.get("/api/v1/intelligence/sectors?type=concept")
    _assert_200_or_degraded(r)
    data = r.json()
    assert "sectors" in data
    if data["sectors"]:
        first = data["sectors"][0]
        for key in ("code", "name", "change_pct"):
            assert key in first


def test_sectors_invalid_type_422(client):
    r = client.get("/api/v1/intelligence/sectors?type=invalid")
    assert r.status_code == 422


def test_dragon_tiger_structure(client):
    r = client.get("/api/v1/intelligence/dragon-tiger")
    _assert_200_or_degraded(r)
    data = r.json()
    assert "stocks" in data


def test_anomalies_structure(client):
    r = client.get("/api/v1/intelligence/anomalies?limit=10")
    _assert_200_or_degraded(r)
    data = r.json()
    assert "anomalies" in data
    if data["anomalies"]:
        first = data["anomalies"][0]
        for key in ("code", "name", "change_pct", "type"):
            assert key in first
        assert first["type"] in ("涨停", "跌停", "振幅异动", "急涨", "急跌")


def test_anomalies_limit_param(client):
    r = client.get("/api/v1/intelligence/anomalies?limit=5")
    _assert_200_or_degraded(r)
    data = r.json()
    assert len(data["anomalies"]) <= 5


def test_announcements_structure(client):
    r = client.get("/api/v1/intelligence/announcements?limit=10")
    _assert_200_or_degraded(r)
    data = r.json()
    assert "announcements" in data
    if data["announcements"]:
        first = data["announcements"][0]
        for key in ("stock", "title", "date"):
            assert key in first


def test_limit_up_bucket_logic():
    """Pure: bucket a pool by consecutive days."""
    pool = [
        {"consecutive_days": 1, "name": "A"},
        {"consecutive_days": 1, "name": "B"},
        {"consecutive_days": 3, "name": "C"},
        {"consecutive_days": 5, "name": "D"},
        {"consecutive_days": 6, "name": "E"},
    ]
    buckets = {}
    for p in pool:
        d = p.get("consecutive_days") or 1
        bucket = "高位板" if d >= 5 else f"{d}板"
        buckets[bucket] = buckets.get(bucket, 0) + 1
    assert buckets == {"1板": 2, "3板": 1, "高位板": 2}


def test_anomaly_classification():
    """Pure: classification thresholds."""
    def classify(chg, amp):
        if chg >= 9.8: return "涨停"
        if chg <= -9.8: return "跌停"
        if (amp or 0) >= 8: return "振幅异动"
        if chg >= 7: return "急涨"
        if chg <= -7: return "急跌"
        return None
    assert classify(10, 5) == "涨停"
    assert classify(-10, 5) == "跌停"
    assert classify(3, 9) == "振幅异动"
    assert classify(8, 4) == "急涨"
    assert classify(-8, 4) == "急跌"
    assert classify(2, 3) is None
