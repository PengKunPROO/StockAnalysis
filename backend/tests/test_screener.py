"""Tests for 选股器 screener: fields, predicates, skills, API, eastmoney helpers."""
import pytest


# ---------- eastmoney helpers (pure) ----------
def test_secid_sh():
    from app.datasources.eastmoney import _secid
    assert _secid("sh.600519") == "1.600519"
    assert _secid("sh.688001") == "1.688001"


def test_secid_sz():
    from app.datasources.eastmoney import _secid
    assert _secid("sz.000001") == "0.000001"
    assert _secid("sz.300750") == "0.300750"


def test_secid_invalid():
    from app.datasources.eastmoney import _secid
    assert _secid("invalid") is None
    assert _secid("") is None


def test_num_handles_bad():
    from app.datasources.eastmoney import _num
    assert _num(None) is None
    assert _num("abc") is None
    assert _num("3.14") == 3.14
    assert _num(42) == 42.0


# ---------- field registry ----------
def test_fields_have_required_keys():
    from app.screener import get_fields
    for f in get_fields():
        d = f.model_dump()
        for key in ("name", "label", "type", "category", "constraints"):
            assert key in d


def test_fields_categories_present():
    from app.screener import get_fields
    cats = {f.category for f in get_fields()}
    assert "基本面" in cats
    assert "行情表现" in cats
    assert "技术信号" in cats


# ---------- predicate matching ----------
def _stock(**kw):
    base = {"code": "sh.600519", "name": "X", "price": 100, "change_pct": 5,
            "volume": 1e6, "amount": 5e8, "amplitude": 3, "turnover": 8,
            "pe_ttm": 25, "pb": 4, "total_market_cap": 2e11, "roe": 20}
    base.update(kw)
    return base


def test_match_passes_when_in_range():
    from app.screener.fields import matches_snapshot
    assert matches_snapshot(_stock(), {"pe_ttm": {"min": 0, "max": 30}})


def test_match_fails_when_out_of_range():
    from app.screener.fields import matches_snapshot
    assert not matches_snapshot(_stock(pe_ttm=50), {"pe_ttm": {"min": 0, "max": 30}})


def test_match_min_only():
    from app.screener.fields import matches_snapshot
    assert matches_snapshot(_stock(roe=20), {"roe": {"min": 15}})
    assert not matches_snapshot(_stock(roe=10), {"roe": {"min": 15}})


def test_match_market_cap_scaled():
    # total_market_cap raw = 2e11 yuan; scale 1e-8 -> 2000 亿; filter min=1000 亿
    from app.screener.fields import matches_snapshot
    assert matches_snapshot(_stock(total_market_cap=2e11), {"total_market_cap": {"min": 1000}})
    assert not matches_snapshot(_stock(total_market_cap=2e11), {"total_market_cap": {"min": 5000}})


def test_match_missing_data_excluded():
    from app.screener.fields import matches_snapshot
    # PE None (loss-making) with a PE filter -> excluded
    assert not matches_snapshot(_stock(pe_ttm=None), {"pe_ttm": {"min": 0, "max": 30}})


def test_match_multiple_fields_all_required():
    from app.screener.fields import matches_snapshot
    vals = {"pe_ttm": {"min": 0, "max": 30}, "roe": {"min": 15}, "change_pct": {"min": 2}}
    assert matches_snapshot(_stock(pe_ttm=25, roe=20, change_pct=5), vals)
    assert not matches_snapshot(_stock(pe_ttm=25, roe=10, change_pct=5), vals)


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


def test_value_skill_fields():
    from app.screener import list_skills
    skills = {s["name"]: s for s in list_skills()}
    v = skills["value"]["fields"]
    assert "pe_ttm" in v
    assert "roe" in v


# ---------- API ----------
def test_api_fields(client):
    r = client.get("/api/v1/screener/fields")
    assert r.status_code == 200
    data = r.json()
    assert "fields" in data
    assert "categories" in data
    assert len(data["fields"]) > 0


def test_api_skills(client):
    r = client.get("/api/v1/screener/skills")
    assert r.status_code == 200
    assert "skills" in r.json()
    assert len(r.json()["skills"]) >= 3


def test_api_run_snapshot_filter(client):
    """Run with only snapshot fields (no per-stock technical pass). Accept results or network warning."""
    r = client.post("/api/v1/screener/run", json={
        "fields": {"pe_ttm": {"min": 0, "max": 30}, "roe": {"min": 15}},
        "sort": "roe", "limit": 10,
    })
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert "count" in data
    # either got results or a network warning - both acceptable
    if data["count"] > 0:
        first = data["results"][0]
        assert "code" in first and "name" in first


def test_api_run_invalid_sort_falls_back(client):
    r = client.post("/api/v1/screener/run", json={
        "fields": {}, "sort": "INVALID_FIELD", "limit": 5,
    })
    assert r.status_code == 200


def test_eastmoney_degrades_gracefully(monkeypatch):
    """When _get_json returns None (network failure caught), fetchers return empty/None, never raise."""
    from app.datasources import eastmoney

    async def _none(*a, **k):
        return None  # simulates _get_json having caught a network error

    monkeypatch.setattr(eastmoney, "_get_json", _none)
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        assert loop.run_until_complete(eastmoney.fetch_market_snapshot()) == []
        assert loop.run_until_complete(eastmoney.fetch_valuation("sh.600519")) is None
        assert loop.run_until_complete(eastmoney.fetch_sector_rank()) == []
        assert loop.run_until_complete(eastmoney.fetch_fund_flow("sh.600519")) == []
        assert loop.run_until_complete(eastmoney.fetch_north_bound()) == []
        assert loop.run_until_complete(eastmoney.fetch_announcements("sh.600519")) == []
    finally:
        loop.close()


def test_get_json_catches_network_error(monkeypatch):
    """_get_json must catch httpx errors and return None (never propagate)."""
    import httpx
    from app.datasources import eastmoney

    class _RaisingClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def get(self, *a, **k):
            raise httpx.ConnectError("simulated")

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _RaisingClient())
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        assert loop.run_until_complete(eastmoney._get_json("http://x", {})) is None
    finally:
        loop.close()
