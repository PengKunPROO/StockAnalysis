"""Tests for 选股器 screener: fields, predicates, skills, API, fuyao helpers."""
import asyncio
import pytest


# ---------- field registry ----------
def test_fields_have_required_keys():
    from app.screener import get_fields
    for f in get_fields():
        d = f.model_dump()
        for key in ("name", "label", "type", "category", "constraints", "available"):
            assert key in d


def test_fields_categories_present():
    from app.screener import get_fields
    cats = {f.category for f in get_fields()}
    assert "基本面" in cats
    assert "行情表现" in cats
    assert "技术信号" in cats


def test_pe_pb_marked_unavailable():
    """PE/PB 估值接口未上线 - 必须标 unavailable 给前端诚实提示。"""
    from app.screener import get_fields
    by_name = {f.name: f for f in get_fields()}
    assert by_name["pe_ttm"].available is False
    assert by_name["pb"].available is False
    assert by_name["total_market_cap"].available is False
    assert by_name["turnover"].available is False
    # amplitude is now computed from (high-low)/prev_close*100 - available
    assert by_name["amplitude"].available is True
    # 可用字段
    assert by_name["change_pct"].available is True
    assert by_name["amount"].available is True
    assert by_name["roe"].available is True


# ---------- Pass1 predicate (snapshot fields: change_pct, amount) ----------
def _stock(**kw):
    base = {"code": "sh.600519", "name": "X", "price": 100, "change_pct": 5,
            "volume": 1e6, "amount": 5e8}
    base.update(kw)
    return base


def test_match_change_pct_in_range():
    from app.screener.fields import matches_snapshot
    assert matches_snapshot(_stock(change_pct=3), {"change_pct": {"min": 0, "max": 10}})


def test_match_change_pct_out_of_range():
    from app.screener.fields import matches_snapshot
    assert not matches_snapshot(_stock(change_pct=15), {"change_pct": {"min": 0, "max": 10}})


def test_match_amount_min():
    from app.screener.fields import matches_snapshot
    assert matches_snapshot(_stock(amount=5e8), {"amount": {"min": 1e8}})
    assert not matches_snapshot(_stock(amount=5e7), {"amount": {"min": 1e8}})


def test_match_skips_non_snapshot_fields():
    """roe/pe_ttm 等 Pass2 字段不在 Pass1 检查 -> matches_snapshot 不影响。"""
    from app.screener.fields import matches_snapshot
    # roe 不在 snapshot，matches_snapshot 应跳过它（不影响结果）
    assert matches_snapshot(_stock(), {"roe": {"min": 15}})


def test_match_missing_data_excluded():
    from app.screener.fields import matches_snapshot
    assert not matches_snapshot(_stock(change_pct=None), {"change_pct": {"min": 0}})


# ---------- Pass2 roe predicate ----------
def test_roe_matches():
    from app.screener.engine import _roe_matches
    assert _roe_matches(20.0, {"min": 15})
    assert not _roe_matches(10.0, {"min": 15})
    assert _roe_matches(20.0, {"min": 15, "max": 30})
    assert not _roe_matches(40.0, {"min": 15, "max": 30})
    assert _roe_matches(None, {"min": 15}) is False  # 缺数据排除


# ---------- skills ----------
def test_skills_list():
    from app.screener import list_skills
    skills = list_skills()
    names = [s["name"] for s in skills]
    assert "value" in names
    assert "technical" in names
    for s in skills:
        for key in ("name", "label", "description", "fields"):
            assert key in s


def test_value_skill_uses_roe():
    from app.screener import list_skills
    v = {s["name"]: s for s in list_skills()}["value"]
    assert "roe" in v["fields"]


# ---------- API ----------
def test_api_fields(client):
    r = client.get("/api/v1/screener/fields")
    assert r.status_code == 200
    data = r.json()
    assert "fields" in data and "categories" in data
    assert len(data["fields"]) > 0


def test_api_skills(client):
    r = client.get("/api/v1/screener/skills")
    assert r.status_code == 200
    assert len(r.json()["skills"]) >= 3


def test_api_run_change_pct_filter(client):
    """Pass1 行情过滤 (change_pct) - 不触发 Pass2 逐个查，快。"""
    r = client.post("/api/v1/screener/run", json={
        "fields": {"change_pct": {"min": 0}}, "sort": "change_pct", "limit": 5,
    })
    assert r.status_code == 200
    data = r.json()
    assert "results" in data and "count" in data
    if data["count"] > 0:
        first = data["results"][0]
        assert "code" in first and "name" in first


def test_api_run_invalid_sort_falls_back(client):
    r = client.post("/api/v1/screener/run", json={"fields": {}, "sort": "INVALID", "limit": 5})
    assert r.status_code == 200


# ---------- fuyao source helpers (degrade) ----------
def test_fuyao_source_available():
    from app.datasources import get_source_for_market
    s = get_source_for_market("a_share")
    assert s is not None
    # new methods exist
    for m in ("fetch_market_snapshot", "fetch_limit_up_pool", "fetch_dragon_tiger",
              "fetch_anomaly_list", "fetch_index_snapshot"):
        assert hasattr(s, m), f"missing {m}"


def test_fuyao_market_snapshot_degrades(monkeypatch):
    from app.datasources.tonghuashun import TonghuashunSource
    async def boom(self, path, params=None):
        raise Exception("net down")
    monkeypatch.setattr(TonghuashunSource, "_get", boom)
    s = TonghuashunSource()
    out = asyncio.run(s.fetch_market_snapshot())
    assert out == []
