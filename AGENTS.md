# AGENTS.md

## Stack
- **Backend**: FastAPI + SQLAlchemy 2.0 async + Pydantic v2, Python 3.11, entry: `backend/app/main.py:app`
- **Frontend**: React 19 + TypeScript ~6.0 + Vite 8, charts: `lightweight-charts`
- **DB**: defaults to SQLite (dev), PostgreSQL 16 via Docker. `database.py` auto-creates tables via `Base.metadata.create_all` (no migrations)
- **Background scheduler**: APScheduler, syncs klines daily at 16:00, cleans old data at 03:00

## Stock code format
Unified: `sh.600519`, `sz.000001`, `us.AAPL`. Always use this format in APIs and DB.

## Commands
```bash
# Backend (from backend/, after activating .venv)
uvicorn app.main:app --host 127.0.0.1 --port 8002

# Frontend (from frontend/)
npm run dev                    # Vite dev, proxies /api → localhost:8002
npm run build                  # tsc --noEmit + vite build
npm run lint                   # oxlint

# Docker (Postgres + backend, port 8000)
docker compose up

# Full test suite (requires bash)
bash verify.sh                 # backend pytest + frontend tsc + vite build + CSS/import integrity checks

# Backend tests only (from backend/, with .venv)
pytest tests/ -v --tb=short

# Single test
pytest tests/test_kline.py -v
```

## Architecture

### Data pipeline
```
datasources (pull raw data) → DataEngine (cache-first via SQLite) → indicators (compute on read)
```
- No pre-computed indicators in DB — store raw OHLCV, compute MACD/RSI/KDJ/BOLL/ATR/fibonacci at query time.
- Datasources implement `DataSourceProtocol` (`backend/app/datasources/base.py`). Registry in `datasources/__init__.py` — order matters (first registered = primary for market).
- Sources: `tonghuashun` (A-share, primary - 含全市场快照/涨停池/连板天梯/龙虎榜/异动/热榜/ticker-list/指数), `akshare` (A-share fallback), `yfinance` (US), `sample` (test/fake).
- **SampleSource 铁律**: `sample` 源仅用于开发兜底，**永远不可缓存到 DB**。`data_engine.py` 检测 `source.name == "sample"` 时跳过 `upsert_daily_klines`，只返回内存数据 + warning。`get_realtime`/`get_financial`/`get_news` 也跳过 sample 源。假数据一旦缓存到 DB，会永久污染后续所有请求（K线、指标、信号、AI解读全部基于假数据）。
- `eastmoney.py` 提供 `fetch_north_bound`(kamt 北向资金), `fetch_sector_rank`(push2 clist 行业/概念板块排行), `fetch_announcements`(np-anotice-stock 公告)。All methods degrade, never raise.
- **同花顺 fuyao API 分页陷阱**: `/api/a-share/prices/historical` 接口忽略 `offset` 参数，每次返回相同全量数据。`fetch_kline` 必须用 `date_ms` 去重并在无新数据时 `break`，否则 `while True` 分页循环会无限运行直到 `asyncio.wait_for(timeout=8s)` 超时。

### API routes
All under `/api/v1/` — router tree: `backend/app/api/v1/router.py`. Endpoints: stocks, financial, search, index, health, indicators, skills, watchlist, diagnosis, news, signals, screener, intelligence.
- `signals/{code}` (rule signals JSON) + `signals/{code}/ai` (SSE: rules first, then DeepSeek stream) — 操作建议
- `screener/{fields,skills,run}` — 选股器 (OCP FilterField registry + two-pass filter over eastmoney market snapshot)
- `intelligence/{overview,limit-up,fund-flow,sectors,dragon-tiger,anomalies,announcements}` — 市场情报 (6 tabs)
Screener/intelligence endpoints degrade gracefully: a failed data source returns empty + `warning`, never 500.

### AI Diagnosis
- Function-calling via DeepSeek API (configurable via env) with SSE streaming.
- Tools defined in `diagnosis/tools.py` → LLM calls `get_kline`, `get_indicators`, `get_financials`, `get_realtime`, `search_stocks`.
- Skills: markdown files in `backend/skills/` with YAML frontmatter (`name`, `description`, `mode`).

### News
- `GET /api/v1/news/stock/{code}` caches results per day. Pass `?refresh=true` to force re-fetch.
- A-share news fetched via `akshare.stock_news_em()` — fast, reliable, no LLM dependency.
- News analysis uses `hermes chat -Q -q --max-turns 1` SSE streaming subprocess.

## Commit & Push
- After fixing a bug or adding a feature, commit and push to `origin/main` immediately.
- Run `pytest tests/ -v --tb=short` (from `backend/`) and `npx tsc --noEmit` (from `frontend/`) before committing.

## Tests
- Fixtures in `backend/tests/conftest.py`: `client` (module-scoped `TestClient`), `stock_code` = `"sh.600519"`.
- Tests requiring `FUYAO_API_KEY` env var are skipped with `@pytest.mark.skipif`.
- All route handlers and DB operations must be `async def`.
- **New features must include tests.** Pre-push hook enforces this.

## Frontend
- Path alias `@/*` → `./src/*`.
- Components: `KlineChart`, `InfoCards`, `DiagnosisPanel`, `NewsPanel`, `SearchBar`, `SkillManager`, `TopTabBar`, `SignalsPanel`, `ScreenerView`, `IntelligenceView`.
- App is a multi-view SPA: TopTabBar switches the 3 views; `activeView` + `signals` live in AppContext.
- `verify.sh` does integrity checks that grep for specific CSS classes (`.kline-container`, `.news-panel`, `.right`) and component imports in `App.tsx`. If you add/rename components, update `verify.sh`.

## Config
- `pydantic-settings` loads from `.env` (copy `.env.example`).
- Default `DATABASE_URL` = `sqlite+aiosqlite:///./stock.db`. Docker overrides to `postgresql+asyncpg://...`.
- `diagnosis_max_tool_rounds` = 5 (max LLM function-calling rounds per chat).
