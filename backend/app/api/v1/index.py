from fastapi import APIRouter, Query
from app.engine.data_engine import engine

router = APIRouter(tags=["index"])


@router.get("/market/index")
async def get_market_index(
    codes: str = Query("sh.000001,us.^GSPC", description="逗号分隔的指数代码"),
):
    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    indices, warning = await engine.get_index(code_list)
    result = {"indices": indices}
    if warning:
        result["warning"] = warning
    return result
