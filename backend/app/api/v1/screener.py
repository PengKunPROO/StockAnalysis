"""选股器 (screener) API: declarative fields, skill presets, two-pass run."""
from fastapi import APIRouter, Query
from pydantic import BaseModel
from app.screener import get_fields, run_screener, list_skills

router = APIRouter(prefix="/screener", tags=["screener"])


@router.get("/fields")
async def fields():
    fl = get_fields()
    categories: list[str] = []
    for f in fl:
        if f.category not in categories:
            categories.append(f.category)
    return {"fields": [f.model_dump() for f in fl], "categories": categories}


@router.get("/skills")
async def skills():
    return {"skills": list_skills()}


class RunRequest(BaseModel):
    fields: dict  # {field_name: {"min":x,"max":y} | True}
    sort: str = "change_pct"
    limit: int = 50


@router.post("/run")
async def run(req: RunRequest):
    sort = req.sort if req.sort in (
        "change_pct", "roe", "debt_ratio", "amplitude", "amount",
        "near_high_drop", "change_5d", "change_20d", "hot_rank", "main_net_flow"
    ) else "change_pct"
    limit = max(1, min(req.limit, 200))
    result = await run_screener(req.fields, sort=sort, limit=limit)
    return result
