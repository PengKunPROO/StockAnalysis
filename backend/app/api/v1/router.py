from fastapi import APIRouter
from . import stocks, financial, search, index, health
from . import indicators, skills_api, watchlist, diagnosis, news

router = APIRouter(prefix="/api/v1")
router.include_router(stocks.router)
router.include_router(financial.router)
router.include_router(search.router)
router.include_router(index.router)
router.include_router(health.router)
router.include_router(indicators.router)
router.include_router(skills_api.router)
router.include_router(watchlist.router)
router.include_router(diagnosis.router)
router.include_router(news.router)
