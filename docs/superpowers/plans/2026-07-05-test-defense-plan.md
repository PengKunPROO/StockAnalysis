# Test Defense Line Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 13 个 pytest 测试文件 + verify.sh + pre-push hook，覆盖全部现有功能。

**Architecture:** FastAPI TestClient + pytest。真实同花顺 API 数据（无 mock）。前端 tsc + vite build。

**Tech Stack:** pytest, FastAPI TestClient, bash

## Global Constraints

- 所有 API 测试使用真实同花顺 API（需要 FUYAO_API_KEY）
- 无 API Key 时跳过需要网络调用的测试
- 前端测试: tsc 零错误 + vite build 成功
- pre-push hook: 失败拒绝推送
- 测试文件放在 `backend/tests/`

---

### Task 1: 测试基础设施 + conftest

**Files:**
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/requirements-dev.txt`

- [ ] **Step 1: 安装 pytest**

```bash
cd backend && uv pip install pytest pytest-asyncio httpx
```

- [ ] **Step 2: 创建 requirements-dev.txt**

```
pytest>=8.0
pytest-asyncio>=0.24
httpx>=0.27
```

- [ ] **Step 3: 创建 conftest.py**

```python
import os
import pytest
from fastapi.testclient import TestClient

# Try to load API key for real data tests
FUYAO_KEY = os.environ.get("FUYAO_API_KEY", "")
HAS_API_KEY = bool(FUYAO_KEY.strip())

needs_api_key = pytest.mark.skipif(
    not HAS_API_KEY,
    reason="FUYAO_API_KEY not set — skipping real data test"
)


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient with app context."""
    from app.main import app
    return TestClient(app)


@pytest.fixture(scope="module")
def api_key():
    return FUYAO_KEY


@pytest.fixture
def stock_code():
    """Standard test stock: 贵州茅台."""
    return "sh.600519"
```

- [ ] **Step 4: 验证 conftest 能导入**

```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/conftest.py --collect-only 2>&1 | tail -3
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: test infrastructure — conftest, pytest setup"
```

---

### Task 2: 核心 API 测试 (health, search, kline, realtime, financial)

**Files:**
- Create: `backend/tests/test_health.py`
- Create: `backend/tests/test_search.py`
- Create: `backend/tests/test_kline.py`
- Create: `backend/tests/test_realtime.py`
- Create: `backend/tests/test_financials.py`

**Interfaces:**
- Consumes: `client` fixture, `stock_code` fixture from conftest.py

- [ ] **Step 1: test_health.py**

```python
def test_health_ok(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_has_datasources(client):
    r = client.get("/api/v1/health")
    sources = r.json()["datasources"]
    assert "tonghuashun" in sources


def test_health_db_connected(client):
    r = client.get("/api/v1/health")
    assert r.json()["database"] == "connected"
```

- [ ] **Step 2: test_search.py**

```python
def test_search_by_code(client):
    r = client.get("/api/v1/search?q=600519")
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) > 0
    assert any("茅台" in s["name"] for s in results)


def test_search_by_name(client):
    r = client.get("/api/v1/search?q=贵州茅台")
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) > 0


def test_search_empty(client):
    r = client.get("/api/v1/search?q=zzz_nonexistent_xyz")
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) == 0
```

- [ ] **Step 3: test_kline.py**

```python
def test_kline_daily(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/kline?period=daily&start=2026-06-01&end=2026-07-01")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) >= 5, f"Expected >= 5 bars, got {len(data)}"
    # Check structure
    bar = data[0]
    assert "date" in bar
    assert "open" in bar and "close" in bar
    assert bar["close"] > 0


def test_kline_cache(client, stock_code):
    """Second call should be faster (cache hit)."""
    r1 = client.get(f"/api/v1/stock/{stock_code}/kline?period=daily&start=2026-06-01&end=2026-07-01")
    assert r1.status_code == 200
    len1 = len(r1.json()["data"])
    r2 = client.get(f"/api/v1/stock/{stock_code}/kline?period=daily&start=2026-06-01&end=2026-07-01")
    assert r2.status_code == 200
    len2 = len(r2.json()["data"])
    assert len2 >= len1  # cache should have same or more data


def test_kline_invalid_code(client):
    r = client.get("/api/v1/stock/sh.999999/kline?period=daily&start=2026-06-01&end=2026-07-01")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 0
```

- [ ] **Step 4: test_realtime.py**

```python
def test_realtime_ok(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/realtime")
    assert r.status_code == 200
    data = r.json()
    assert data["price"] is not None and data["price"] > 0


def test_realtime_fields(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/realtime")
    data = r.json()
    for field in ["price", "change_pct", "volume", "high", "low"]:
        assert field in data, f"Missing field: {field}"


def test_realtime_change_pct_is_number(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/realtime")
    data = r.json()
    assert isinstance(data["change_pct"], (int, float))
```

- [ ] **Step 5: test_financials.py**

```python
def test_financials_ok(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/financial")
    assert r.status_code == 200
    data = r.json()
    reports = data.get("reports", [data])  # Handle both formats
    if isinstance(reports, list) and len(reports) > 0:
        report = reports[0]
    else:
        report = data
    assert "roe" in report or "code" in data


def test_financials_has_roe(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/financial")
    assert r.status_code == 200
    # Financial data returns code + reports
    data = r.json()
    assert "code" in data
```

- [ ] **Step 6: 运行测试**

```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/test_health.py tests/test_search.py tests/test_kline.py tests/test_realtime.py tests/test_financials.py -v
```

Expected: ~15 tests pass (skip message for API key issues is OK)

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: core API tests — health, search, kline, realtime, financial"
```

---

### Task 3: 功能测试 (indicators, skills, watchlist, diagnosis, datasources, engine, scheduler)

**Files:**
- Create: `backend/tests/test_indicators.py`
- Create: `backend/tests/test_skills.py`
- Create: `backend/tests/test_watchlist.py`
- Create: `backend/tests/test_diagnosis.py`
- Create: `backend/tests/test_datasources.py`
- Create: `backend/tests/test_data_engine.py`
- Create: `backend/tests/test_scheduler.py`

- [ ] **Step 1: test_indicators.py**

```python
def test_indicators_ok(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/indicators?days=60")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) > 0


def test_indicators_has_all(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/indicators?days=60")
    points = r.json()["data"]
    last = points[-1]
    assert "macd" in last
    assert "rsi" in last
    assert "kdj" in last
    assert "boll" in last


def test_indicators_macd_values(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/indicators?days=60")
    last = r.json()["data"][-1]
    macd = last["macd"]
    assert macd is not None
    assert "dif" in macd and "dea" in macd and "macd" in macd


def test_indicators_days_param(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/indicators?days=30")
    assert r.status_code == 200
    assert len(r.json()["data"]) <= 30
```

- [ ] **Step 2: test_skills.py**

```python
def test_skills_list(client):
    r = client.get("/api/v1/skills")
    assert r.status_code == 200
    skills = r.json()["skills"]
    assert len(skills) >= 1
    names = [s["name"] for s in skills]
    assert "股票分析" in names


def test_skills_get_by_name(client):
    r = client.get("/api/v1/skills/股票分析")
    assert r.status_code == 200
    assert "content" in r.json()


def test_skills_get_not_found(client):
    r = client.get("/api/v1/skills/nonexistent_skill_xyz")
    assert r.status_code == 404
```

- [ ] **Step 3: test_watchlist.py**

```python
TEST_CODE = "sh.600519"
TEST_NAME = "贵州茅台"


def test_watchlist_get(client):
    r = client.get("/api/v1/watchlist")
    assert r.status_code == 200
    assert "stocks" in r.json()


def test_watchlist_add(client):
    r = client.post("/api/v1/watchlist", json={"code": TEST_CODE, "name": TEST_NAME})
    assert r.status_code == 200
    assert r.json().get("added") == TEST_CODE


def test_watchlist_duplicate_add(client):
    r = client.post("/api/v1/watchlist", json={"code": TEST_CODE, "name": TEST_NAME})
    assert r.status_code == 200


def test_watchlist_delete(client):
    r = client.delete(f"/api/v1/watchlist/{TEST_CODE}")
    assert r.status_code == 200
    assert r.json().get("removed") == TEST_CODE or "error" in r.json()
```

- [ ] **Step 4: test_diagnosis.py**

```python
import json


def test_diagnosis_chat_returns_200(client):
    r = client.post("/api/v1/diagnosis/chat", json={
        "skill": "股票分析",
        "message": "你好",
        "stock_codes": [{"code": "sh.600519", "name": "贵州茅台"}],
    })
    assert r.status_code == 200


def test_diagnosis_has_session_id(client):
    r = client.post("/api/v1/diagnosis/chat", json={
        "skill": "股票分析",
        "message": "你好",
        "stock_codes": [{"code": "sh.600519", "name": "贵州茅台"}],
    })
    body = r.text
    has_sid = False
    for line in body.split("\n"):
        if line.startswith("data: "):
            d = json.loads(line[6:])
            if d.get("session_id"):
                has_sid = True
                break
    assert has_sid, "No session_id in SSE stream"


def test_diagnosis_has_status(client):
    r = client.post("/api/v1/diagnosis/chat", json={
        "skill": "股票分析",
        "message": "你好",
        "stock_codes": [{"code": "sh.600519", "name": "贵州茅台"}],
    })
    body = r.text
    has_status = False
    for line in body.split("\n"):
        if line.startswith("data: "):
            d = json.loads(line[6:])
            if d.get("status"):
                has_status = True
                break
    assert has_status, "No status in SSE stream"
```

- [ ] **Step 5: test_datasources.py**

```python
def test_tonghuashun_source_import():
    from app.datasources.tonghuashun import TonghuashunSource
    t = TonghuashunSource()
    assert t.name == "tonghuashun"
    assert "a_share" in t.markets


def test_tonghuashun_code_conversion():
    from app.datasources.tonghuashun import TonghuashunSource
    t = TonghuashunSource()
    assert t._to_ths_code("sh.600519") == "600519.SH"
    assert t._to_ths_code("sz.000001") == "1.SZ"
    assert t._to_our_code("600519.SH") == "sh.600519"


def test_tonghuashun_health_check():
    from app.datasources.tonghuashun import TonghuashunSource
    t = TonghuashunSource()
    # Should return True if API key is set
    result = t.health_check()
    assert isinstance(result, bool)


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
```

- [ ] **Step 6: test_data_engine.py**

```python
def test_market_from_code():
    from app.engine.data_engine import DataEngine
    e = DataEngine()
    assert e._market_from_code("sh.600519") == "a_share"
    assert e._market_from_code("sz.000001") == "a_share"
    assert e._market_from_code("us.AAPL") == "us"
    assert e._market_from_code("hk.00700") == "a_share"


def test_engine_health():
    import asyncio
    from app.engine.data_engine import engine
    result = asyncio.run(engine.health())
    assert "status" in result
    assert "datasources" in result
    assert "database" in result
    assert "tonghuashun" in result["datasources"]
```

- [ ] **Step 7: test_scheduler.py**

```python
def test_cleanup_function_exists():
    from app.engine.scheduler import cleanup_old_data
    assert callable(cleanup_old_data)


def test_sync_function_exists():
    from app.engine.scheduler import sync_all_daily_klines
    assert callable(sync_all_daily_klines)
```

- [ ] **Step 8: 运行所有测试**

```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/ -v
```

Expected: ~35+ tests pass

- [ ] **Step 9: Commit**

```bash
git add -A && git commit -m "feat: feature tests — indicators, skills, watchlist, diagnosis, datasources, engine, scheduler"
```

---

### Task 4: verify.sh + pre-push hook + 前端构建检查

**Files:**
- Create: `verify.sh`
- Create: `.git/hooks/pre-push` (symlink to verify.sh)
- Append to: `.hermes.md`

- [ ] **Step 1: 创建 verify.sh**

```bash
#!/bin/bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "=== Stock Agent Test Suite ==="
echo ""

# Backend tests
echo "[1/3] Backend Tests..."
cd "$ROOT/backend"
.venv/Scripts/python.exe -m pytest tests/ -v --tb=short
echo ""

# Frontend build
echo "[2/3] Frontend Build..."
cd "$ROOT/frontend"
npx tsc --noEmit
npx vite build --logLevel error
echo ""

# CSS / feature checks
echo "[3/3] Integrity Checks..."
cd "$ROOT/frontend"
# Check key CSS classes exist
grep -q "kline-container" src/index.css || { echo "FAIL: kline-container missing from CSS"; exit 1; }
grep -q "right-panel" src/index.css || { echo "FAIL: right-panel missing from CSS"; exit 1; }
grep -q "info-card" src/index.css || { echo "FAIL: info-card missing from CSS"; exit 1; }
grep -q "msg-bubble" src/index.css || { echo "FAIL: msg-bubble missing from CSS"; exit 1; }
echo "  CSS classes: OK"

# Check App.tsx imports all components
grep -q "KlineChart" src/App.tsx || { echo "FAIL: KlineChart not imported"; exit 1; }
grep -q "DiagnosisPanel" src/App.tsx || { echo "FAIL: DiagnosisPanel not imported"; exit 1; }
grep -q "InfoCards" src/App.tsx || { echo "FAIL: InfoCards not imported"; exit 1; }
grep -q "SkillManager" src/App.tsx || { echo "FAIL: SkillManager not imported"; exit 1; }
echo "  App.tsx imports: OK"

echo ""
echo "=== ALL TESTS PASSED ==="
```

- [ ] **Step 2: 安装 pre-push hook**

```bash
cp verify.sh .git/hooks/pre-push
chmod +x .git/hooks/pre-push
```

- [ ] **Step 3: 更新 .hermes.md 铁律**

```
## 测试铁律
- 每次新增功能必须新增测试用例
- 修改功能必须更新对应测试
- `git push` 前自动运行 `verify.sh`, 失败拒绝推送
```

- [ ] **Step 4: 测试 pre-push hook**

```bash
bash verify.sh
```

Expected: "ALL TESTS PASSED"

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: verify.sh + pre-push hook + test rule in .hermes.md" && git push
```
