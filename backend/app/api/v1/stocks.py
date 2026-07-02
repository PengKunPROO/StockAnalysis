import uuid
from fastapi import APIRouter, Query, HTTPException
from app.engine.data_engine import engine

router = APIRouter(tags=["stocks"])


@router.get("/stock/{code}/kline")
async def get_stock_kline(
    code: str,
    period: str = Query("daily", pattern=r"^(daily|weekly|monthly)$"),
    start: str = Query("2024-01-01"),
    end: str = Query("2026-12-31"),
):
    data, warning = await engine.get_klines(code, period, start, end)
    result = {"code": code, "period": period, "data": data, "count": len(data)}
    if warning:
        result["warning"] = warning
    return result


@router.get("/stock/{code}/realtime")
async def get_stock_realtime(code: str):
    data, warning = await engine.get_realtime(code)
    if data is None and warning is None:
        raise HTTPException(status_code=404, detail={
            "error": f"未找到股票 {code}", "request_id": str(uuid.uuid4()),
        })
    if data is None:
        raise HTTPException(status_code=503, detail={
            "error": warning, "request_id": str(uuid.uuid4()),
        })
    if warning:
        data["warning"] = warning
    return data
