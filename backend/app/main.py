"""FastAPI application entry point."""
import uuid
import logging
import os
import threading
import webbrowser
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.v1.router import router as v1_router
from app.db.database import init_db, dispose_engine
from app.engine.data_engine import engine
from app.engine.scheduler import start_scheduler, scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Auto-open browser on startup (only when not in debug/reload mode)
_open_browser = os.environ.get("STOCK_AGENT_NO_BROWSER") != "1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Stock Agent backend...")
    await init_db()
    logger.info("Database tables created")
    try:
        start_scheduler()
    except Exception as e:
        logger.warning(f"Scheduler not started: {e}")
    # Health check in background (don't block startup - it takes 12s+ due to datasource checks)
    import asyncio as _asyncio
    async def _bg_health():
        try:
            health = await engine.health()
            logger.info(f"Startup health: {health}")
        except Exception as e:
            logger.warning(f"Startup health check failed: {e}")
    _asyncio.create_task(_bg_health())

    # Auto-open browser after short delay
    if _open_browser:
        def _open():
            import time
            time.sleep(1.5)
            webbrowser.open("http://localhost:8002")
        threading.Thread(target=_open, daemon=True).start()

    yield
    logger.info("Shutting down...")
    try:
        if scheduler.running:
            scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")
    except Exception as e:
        logger.warning(f"Scheduler shutdown error: {e}")
    try:
        await dispose_engine()
        logger.info("Database engine disposed")
    except Exception as e:
        logger.warning(f"DB engine dispose error: {e}")


app = FastAPI(
    title="Stock Agent API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "内部错误", "request_id": str(uuid.uuid4())},
    )


# Mount frontend static files (built by `npm run build`)
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if _STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=_STATIC_DIR / "assets"), name="assets")


@app.get("/")
async def root():
    # Serve frontend index.html if it exists, otherwise return API info
    index = _STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"app": "Stock Agent", "version": "0.1.0", "docs": "/docs"}


# SPA fallback: any non-API route returns index.html
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse(status_code=404, content={"error": "Not found"})
    index = _STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse(status_code=404, content={"error": "Frontend not built. Run: cd frontend && npm run build"})
