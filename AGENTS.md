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
- No pre-computed indicators in DB — store raw OHLCV, compute MACD/RSI/KDJ/BOLL at query time.
- Datasources implement `DataSourceProtocol` (`backend/app/datasources/base.py`). Registry in `datasources/__init__.py` — order matters (first registered = primary for market).
- Three sources: `tonghuashun` (A-share), `yfinance` (US), `sample` (test/fake data).

### API routes
All under `/api/v1/` — router tree: `backend/app/api/v1/router.py`. Endpoints: stocks, financial, search, index, health, indicators, skills, watchlist, diagnosis, news.

### AI Diagnosis
- Function-calling via DeepSeek API (configurable via env) with SSE streaming.
- Tools defined in `diagnosis/tools.py` → LLM calls `get_kline`, `get_indicators`, `get_financials`, `get_realtime`, `search_stocks`.
- Skills: markdown files in `backend/skills/` with YAML frontmatter (`name`, `description`, `mode`).

### News
- `GET /api/v1/news/stock/{code}` caches results per day. Pass `?refresh=true` to force re-fetch via LLM subprocess.
- News fetching calls `hermes chat -Q -q --max-turns 1` subprocess (requires `hermes` CLI in PATH).
- Analysis uses SSE streaming from the same `hermes` subprocess.

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
- Components: `KlineChart`, `InfoCards`, `DiagnosisPanel`, `NewsPanel`, `SearchBar`, `SkillManager`.
- `verify.sh` does integrity checks that grep for specific CSS classes (`.kline-container`, `.right-panel`, `.info-card`) and component imports in `App.tsx`. If you add/rename components, update `verify.sh`.

## Config
- `pydantic-settings` loads from `.env` (copy `.env.example`).
- Default `DATABASE_URL` = `sqlite+aiosqlite:///./stock.db`. Docker overrides to `postgresql+asyncpg://...`.
- `diagnosis_max_tool_rounds` = 5 (max LLM function-calling rounds per chat).
