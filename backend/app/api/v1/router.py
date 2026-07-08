from fastapi import APIRouter
from . import stocks, financial, search, index, health
from . import indicators, skills_api, watchlist, diagnosis, news
from . import signals
from . import screener
from . import intelligence

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
router.include_router(signals.router)
router.include_router(screener.router)
router.include_router(intelligence.router)
