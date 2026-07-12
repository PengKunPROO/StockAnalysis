# backend/app/api/v1/portfolio.py
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal
from app.db.database import get_session_factory
from app.db import queries
from app.db.models import Holding, Transaction

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


# === Request Models ===

class HoldingCreate(BaseModel):
    code: str
    name: str
    shares: int = Field(gt=0)
    avg_cost: float = Field(gt=0)
    buy_date: date


class TransactionCreate(BaseModel):
    code: str
    name: str
    action: str = Field(pattern=r"^(buy|sell)$")
    shares: int = Field(gt=0)
    price: float = Field(gt=0)
    traded_at: datetime
    note: str | None = None


# === Holdings ===

@router.get("/holdings")
async def get_holdings():
    factory = get_session_factory()
    async with factory() as session:
        holdings = await queries.get_holdings(session, only_open=True)
        return {"holdings": [
            {
                "id": h.id, "code": h.code, "name": h.name,
                "shares": h.shares, "avg_cost": float(h.avg_cost),
                "buy_date": str(h.buy_date) if h.buy_date else None,
                "status": h.status, "updated_at": str(h.updated_at),
            }
            for h in holdings
        ]}


@router.post("/holdings")
async def create_holding(item: HoldingCreate):
    factory = get_session_factory()
    async with factory() as session:
        holding = await queries.create_holding(
            session, item.code, item.name,
            item.shares, item.avg_cost, item.buy_date
        )
        return {
            "id": holding.id, "code": holding.code, "name": holding.name,
            "shares": holding.shares, "avg_cost": float(holding.avg_cost),
            "buy_date": str(holding.buy_date), "status": holding.status,
        }


@router.patch("/holdings/{holding_id}")
async def update_holding(holding_id: int, shares: int | None = None, avg_cost: float | None = None):
    factory = get_session_factory()
    async with factory() as session:
        kwargs = {}
        if shares is not None:
            kwargs["shares"] = shares
        if avg_cost is not None:
            kwargs["avg_cost"] = avg_cost
        holding = await queries.update_holding(session, holding_id, **kwargs)
        if not holding:
            raise HTTPException(status_code=404, detail="Holding not found")
        return {"id": holding.id, "shares": holding.shares, "avg_cost": float(holding.avg_cost)}


@router.delete("/holdings/{holding_id}")
async def delete_holding(holding_id: int):
    factory = get_session_factory()
    async with factory() as session:
        await queries.delete_holding(session, holding_id)
        return {"deleted": holding_id}


# === Transactions ===

@router.get("/transactions")
async def get_transactions(
    code: str = Query(default=""),
    action: str = Query(default="", pattern=r"^(buy|sell|)$"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    factory = get_session_factory()
    async with factory() as session:
        txs = await queries.get_transactions(
            session, code=code or None, action=action or None,
            page=page, limit=limit
        )
        total = await queries.count_transactions(
            session, code=code or None, action=action or None
        )
        import math
        return {
            "transactions": [
                {
                    "id": t.id, "code": t.code, "name": t.name,
                    "action": t.action, "shares": t.shares,
                    "price": float(t.price), "amount": float(t.amount),
                    "traded_at": str(t.traded_at), "note": t.note,
                }
                for t in txs
            ],
            "total": total, "page": page,
            "total_pages": math.ceil(total / limit) if limit > 0 else 1,
        }


@router.post("/transactions")
async def create_transaction(item: TransactionCreate):
    factory = get_session_factory()
    async with factory() as session:
        tx = await queries.create_transaction(
            session, item.code, item.name, item.action,
            item.shares, item.price, item.traded_at, item.note
        )
        # Auto-update holding
        holding = await queries.get_holding_by_code(session, item.code)
        if item.action == "buy":
            if holding:
                # 加仓: 重算 avg_cost
                new_shares = holding.shares + item.shares
                new_avg = (holding.shares * float(holding.avg_cost) + item.shares * item.price) / new_shares
                await queries.update_holding(
                    session, holding.id,
                    shares=new_shares, avg_cost=round(new_avg, 4)
                )
            else:
                # 新建持仓
                await queries.create_holding(
                    session, item.code, item.name,
                    item.shares, item.price, item.traded_at.date()
                )
        elif item.action == "sell":
            if holding:
                new_shares = holding.shares - item.shares
                if new_shares <= 0:
                    await queries.update_holding(session, holding.id, shares=0, status="closed")
                else:
                    await queries.update_holding(session, holding.id, shares=new_shares)
        return {
            "id": tx.id, "code": tx.code, "action": tx.action,
            "shares": tx.shares, "price": float(tx.price),
            "amount": float(tx.amount), "traded_at": str(tx.traded_at),
        }


@router.delete("/transactions/{tx_id}")
async def delete_transaction(tx_id: int):
    factory = get_session_factory()
    async with factory() as session:
        await queries.delete_transaction(session, tx_id)
        return {"deleted": tx_id}
