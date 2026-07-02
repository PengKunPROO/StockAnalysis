"""FastAPI application entry point."""
import uuid
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.v1.router import router as v1_router
from app.db.database import init_db
from app.engine.data_engine import engine
from app.engine.scheduler import start_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Stock Agent backend...")
    await init_db()
    logger.info("Database tables created")
    try:
        start_scheduler()
    except Exception as e:
        logger.warning(f"Scheduler not started: {e}")
    health = await engine.health()
    logger.info(f"Startup health: {health}")
    yield
    logger.info("Shutting down...")


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


@app.get("/")
async def root():
    return {"app": "Stock Agent", "version": "0.1.0", "docs": "/docs"}
