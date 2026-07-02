import uuid
from fastapi import APIRouter, HTTPException
from app.engine.data_engine import engine

router = APIRouter(tags=["financial"])


@router.get("/stock/{code}/financial")
async def get_stock_financial(code: str):
    data, warning = await engine.get_financial(code)
    if data is None:
        raise HTTPException(status_code=404, detail={
            "error": f"未找到 {code} 的财务数据", "request_id": str(uuid.uuid4()),
        })
    result = {"code": code, "reports": [data]}
    if warning:
        result["warning"] = warning
    return result
