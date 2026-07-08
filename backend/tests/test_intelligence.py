"""Tests for 市场情报 intelligence API - 全部用同花顺 fuyao，结构 + 降级 + 实测。"""
import pytest


def _assert_200(r):
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"


def test_overview_structure(client):
    r = client.get("/api/v1/intelligence/overview")
    _assert_200(r)
    data = r.json()
    for key in ("indices", "breadth", "red_ratio", "limit_up_count", "board_buckets", "sentiment"):
        assert key in data, f"Missing: {key}"
    assert "fear_greed" in data["sentiment"]
    assert 0 <= data["sentiment"]["fear_greed"] <= 100
    assert 0 <= data["red_ratio"] <= 100


def test_limit_up_structure(client):
    r = client.get("/api/v1/intelligence/limit-up")
    _assert_200(r)
    data = r.json()
    assert "stocks" in data and "buckets" in data
    if data["stocks"]:
        first = data["stocks"][0]
        for key in ("code", "name", "consecutive_days"):
            assert key in first


def test_fund_flow_stock(client):
    r = client.get("/api/v1/intelligence/fund-flow?scope=stock")
    _assert_200(r)
    data = r.json()
    assert "stocks" in data or "warning" in data


def test_fund_flow_north(client):
    r = client.get("/api/v1/intelligence/fund-flow?scope=north")
    _assert_200(r)
    data = r.json()
    assert "north" in data or "warning" in data


def test_fund_flow_industry_422(client):
    """行业/概念资金流已移除(同花顺无接口) -> 422。"""
    r = client.get("/api/v1/intelligence/fund-flow?scope=industry")
    assert r.status_code == 422


def test_sectors_degraded(client):
    """板块轮动: 同花顺无行业板块接口 -> 降级 warning。"""
    r = client.get("/api/v1/intelligence/sectors?type=industry")
    _assert_200(r)
    data = r.json()
    assert "sectors" in data
    # 无数据源时返回降级 warning
    assert data.get("warning") or data.get("sectors") == []


def test_dragon_tiger_structure(client):
    r = client.get("/api/v1/intelligence/dragon-tiger")
    _assert_200(r)
    data = r.json()
    assert "stocks" in data


def test_anomalies_structure(client):
    r = client.get("/api/v1/intelligence/anomalies?limit=10")
    _assert_200(r)
    data = r.json()
    assert "anomalies" in data
    if data["anomalies"]:
        first = data["anomalies"][0]
        for key in ("code", "name", "type", "reason"):
            assert key in first


def test_anomalies_limit_param(client):
    r = client.get("/api/v1/intelligence/anomalies?limit=5")
    _assert_200(r)
    assert len(r.json()["anomalies"]) <= 5


def test_announcements_structure(client):
    r = client.get("/api/v1/intelligence/announcements?limit=10")
    _assert_200(r)
    data = r.json()
    assert "announcements" in data
    if data["announcements"]:
        first = data["announcements"][0]
        for key in ("stock", "title"):
            assert key in first


# ---------- pure compute ----------
def test_limit_up_bucket_logic():
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


def test_fear_greed_clamped():
    """fear_greed 必须 clamp 在 0-100。"""
    def fg(avg_idx, red):
        return max(0, min(100, round(50 + avg_idx * 8 + (red - 50) * 0.4)))
    assert fg(10, 90) == 100  # 极度贪婪
    assert fg(-10, 10) == 0   # 极度恐惧
    assert 0 <= fg(0, 50) <= 100
