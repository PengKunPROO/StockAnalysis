from datetime import date
from sqlalchemy import select, func, or_
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.db.models import Stock, DailyKline, Financial, SyncLog


async def upsert_stock(session, code: str, name: str, market: str, industry: str = ""):
    stmt = sqlite_insert(Stock).values(
        code=code, name=name, market=market, industry=industry
    ).on_conflict_do_update(
        index_elements=["code"],
        set_={"name": name, "industry": industry, "updated_at": func.now()},
    )
    await session.execute(stmt)


async def upsert_daily_klines(session, code: str, bars: list[dict]):
    for bar in bars:
        stmt = sqlite_insert(DailyKline).values(code=code, **bar).on_conflict_do_update(
            index_elements=["code", "trade_date"],
            set_={
                "open": bar["open"], "high": bar["high"],
                "low": bar["low"], "close": bar["close"],
                "volume": bar["volume"], "amount": bar["amount"],
            },
        )
        await session.execute(stmt)


async def upsert_financials(session, code: str, report: dict):
    stmt = sqlite_insert(Financial).values(code=code, **report).on_conflict_do_update(
        index_elements=["code", "report_date"],
        set_={k: v for k, v in report.items() if k != "report_date"},
    )
    await session.execute(stmt)


async def get_daily_klines(session, code: str, start: str, end: str) -> list[dict]:
    result = await session.execute(
        select(DailyKline)
        .where(DailyKline.code == code)
        .where(DailyKline.trade_date >= start)
        .where(DailyKline.trade_date <= end)
        .order_by(DailyKline.trade_date.asc())
    )
    rows = result.scalars().all()
    return [
        {
            "date": str(r.trade_date),
            "open": float(r.open) if r.open else 0,
            "high": float(r.high) if r.high else 0,
            "low": float(r.low) if r.low else 0,
            "close": float(r.close) if r.close else 0,
            "volume": int(r.volume) if r.volume else 0,
            "amount": float(r.amount) if r.amount else 0,
        }
        for r in rows
    ]


async def get_max_trade_date(session, code: str) -> date | None:
    result = await session.execute(
        select(func.max(DailyKline.trade_date)).where(DailyKline.code == code)
    )
    return result.scalar()


async def get_latest_financial(session, code: str) -> dict | None:
    result = await session.execute(
        select(Financial)
        .where(Financial.code == code)
        .order_by(Financial.report_date.desc())
        .limit(1)
    )
    row = result.scalar()
    if row is None:
        return None
    return {
        "report_date": str(row.report_date),
        "revenue": float(row.revenue) if row.revenue else None,
        "net_profit": float(row.net_profit) if row.net_profit else None,
        "pe_ratio": float(row.pe_ratio) if row.pe_ratio else None,
        "pb_ratio": float(row.pb_ratio) if row.pb_ratio else None,
        "roe": float(row.roe) if row.roe else None,
        "debt_ratio": float(row.debt_ratio) if row.debt_ratio else None,
        "total_assets": float(row.total_assets) if row.total_assets else None,
        "total_equity": float(row.total_equity) if row.total_equity else None,
    }


async def search_stocks_db(session, keyword: str) -> list[dict]:
    pattern = f"%{keyword}%"
    result = await session.execute(
        select(Stock).where(
            or_(Stock.code.ilike(pattern), Stock.name.ilike(pattern))
        ).limit(20)
    )
    rows = result.scalars().all()
    return [
        {
            "code": r.code,
            "name": r.name,
            "market": r.market,
            "industry": r.industry or "",
        }
        for r in rows
    ]


async def log_sync(session, source: str, data_type: str, code: str | None,
                   status: str, rows_count: int = 0, error_msg: str | None = None):
    entry = SyncLog(
        source=source, data_type=data_type, code=code,
        status=status, rows_count=rows_count, error_msg=error_msg,
        started_at=func.now(), finished_at=func.now(),
    )
    session.add(entry)
    await session.flush()


async def get_all_tracked_codes(session) -> list[str]:
    result = await session.execute(select(Stock.code))
    return [row[0] for row in result.fetchall()]
