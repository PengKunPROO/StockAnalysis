from fastapi import APIRouter, Query
from pydantic import BaseModel
from app.db.database import get_session_factory
from app.db.models import Stock

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistItem(BaseModel):
    code: str
    name: str
    group_name: str = "默认分组"


class MoveItem(BaseModel):
    code: str
    group_name: str


@router.get("")
async def get_watchlist(group: str = Query(default="", description="分组名，空=全部")):
    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select
        if group:
            result = await session.execute(
                select(Stock).where(Stock.group_name == group)
            )
        else:
            result = await session.execute(select(Stock))
        stocks = result.scalars().all()
        return {"stocks": [
            {"code": s.code, "name": s.name, "market": s.market, "group_name": s.group_name or "默认分组"}
            for s in stocks
        ]}


@router.get("/groups")
async def get_groups():
    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select, distinct
        result = await session.execute(select(distinct(Stock.group_name)))
        groups = [r[0] or "默认分组" for r in result.all()]
        return {"groups": sorted(set(groups))}


@router.post("")
async def add_to_watchlist(item: WatchlistItem):
    from app.db import queries
    factory = get_session_factory()
    async with factory() as session:
        market = "us" if item.code.startswith("us.") else "a_share"
        await queries.upsert_stock(session, item.code, item.name, market, "")
        # Set group name
        from sqlalchemy import update
        await session.execute(
            update(Stock).where(Stock.code == item.code).values(group_name=item.group_name)
        )
        await session.commit()
    return {"added": item.code}


@router.patch("/move")
async def move_to_group(item: MoveItem):
    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import update
        await session.execute(
            update(Stock).where(Stock.code == item.code).values(group_name=item.group_name)
        )
        await session.commit()
    return {"moved": item.code, "group": item.group_name}


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
