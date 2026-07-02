from fastapi import APIRouter, Query
from app.engine.data_engine import engine

router = APIRouter(tags=["search"])


@router.get("/search")
async def search_stocks(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    market: str | None = Query(None, pattern=r"^(a_share|us)$"),
):
    results, warning = await engine.search(q)
    if market:
        results = [r for r in results if r["market"] == market]
    return {"results": results, "count": len(results)}
