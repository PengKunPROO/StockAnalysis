from fastapi import APIRouter, Query
from app.engine.data_engine import engine
from app.indicators import compute_all

router = APIRouter(tags=["indicators"])


@router.get("/stock/{code}/indicators")
async def get_indicators(
    code: str,
    period: str = Query("daily", pattern=r"^(daily|weekly|monthly)$"),
    days: int = Query(60, ge=20, le=500),
):
    from datetime import date, timedelta
    end = str(date.today())
    start = str(date.today() - timedelta(days=days * 2))
    klines, _ = await engine.get_klines(code, period, start, end)
    indicators = await compute_all(klines[-days:]) if klines else []
    return {"code": code, "period": period, "data": indicators}
