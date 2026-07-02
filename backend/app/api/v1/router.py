from fastapi import APIRouter
from . import stocks, financial, search, index, health

router = APIRouter(prefix="/api/v1")
router.include_router(stocks.router)
router.include_router(financial.router)
router.include_router(search.router)
router.include_router(index.router)
router.include_router(health.router)
