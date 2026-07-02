from fastapi import APIRouter
from pydantic import BaseModel
from app.db.database import get_session_factory
from app.db.models import Stock

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistItem(BaseModel):
    code: str
    name: str


@router.get("")
async def get_watchlist():
    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select
        result = await session.execute(select(Stock))
        stocks = result.scalars().all()
        return {"stocks": [{"code": s.code, "name": s.name, "market": s.market} for s in stocks]}


@router.post("")
async def add_to_watchlist(item: WatchlistItem):
    from app.db import queries
    factory = get_session_factory()
    async with factory() as session:
        market = "us" if item.code.startswith("us.") else "a_share"
        await queries.upsert_stock(session, item.code, item.name, market, "")
        await session.commit()
    return {"added": item.code}


@router.delete("/{code}")
async def remove_from_watchlist(code: str):
    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select, delete
        result = await session.execute(select(Stock).where(Stock.code == code))
        stock = result.scalar_one_or_none()
        if stock:
            await session.execute(delete(Stock).where(Stock.code == code))
            await session.commit()
            return {"removed": code}
        return {"error": "Not found"}
