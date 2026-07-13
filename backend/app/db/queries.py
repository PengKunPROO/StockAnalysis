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
    # Convert "2026-3" → date(2026, 9, 30)
    rd = report.get("report_date", "")
    if "-" in str(rd):
        parts = str(rd).split("-")
        y, q = int(parts[0]), int(parts[1])
        month = q * 3
        report["report_date"] = date(y, month, 1)
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


async def get_kline_range(session, code: str) -> tuple:
    """Return (min_date, max_date, count) for cached klines."""
    result = await session.execute(
        select(
            func.min(DailyKline.trade_date),
            func.max(DailyKline.trade_date),
            func.count(DailyKline.trade_date),
        ).where(DailyKline.code == code)
    )
    return result.one()


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


# === Portfolio: Holdings, Transactions, Reports ===

import uuid
from app.db.models import (
    Holding, Transaction, DailyReport, ReportSection, ReportContext
)


# --- Holdings ---

async def create_holding(session, code, name, shares, avg_cost, buy_date):
    holding = Holding(
        code=code, name=name, shares=shares,
        avg_cost=avg_cost, buy_date=buy_date, status="open"
    )
    session.add(holding)
    await session.commit()
    await session.refresh(holding)
    return holding


async def get_holdings(session, only_open=True):
    stmt = select(Holding)
    if only_open:
        stmt = stmt.where(Holding.status == "open")
    stmt = stmt.order_by(Holding.updated_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_holding_by_code(session, code):
    result = await session.execute(
        select(Holding).where(Holding.code == code, Holding.status == "open")
    )
    return result.scalar_one_or_none()


async def update_holding(session, holding_id, **kwargs):
    from sqlalchemy import update as sa_update
    await session.execute(
        sa_update(Holding).where(Holding.id == holding_id).values(**kwargs)
    )
    await session.commit()
    result = await session.execute(select(Holding).where(Holding.id == holding_id))
    return result.scalar_one_or_none()


async def delete_holding(session, holding_id):
    from sqlalchemy import delete as sa_delete
    await session.execute(sa_delete(Holding).where(Holding.id == holding_id))
    await session.commit()


# --- Transactions ---

async def create_transaction(session, code, name, action, shares, price, traded_at, note=None):
    tx = Transaction(
        code=code, name=name, action=action,
        shares=shares, price=price,
        amount=shares * price, traded_at=traded_at, note=note
    )
    session.add(tx)
    await session.commit()
    await session.refresh(tx)
    return tx


async def get_transactions(session, code=None, action=None, page=1, limit=20):
    stmt = select(Transaction)
    if code:
        stmt = stmt.where(Transaction.code == code)
    if action:
        stmt = stmt.where(Transaction.action == action)
    stmt = stmt.order_by(Transaction.traded_at.desc())
    stmt = stmt.offset((page - 1) * limit).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_transactions(session, code=None, action=None):
    stmt = select(func.count()).select_from(Transaction)
    if code:
        stmt = stmt.where(Transaction.code == code)
    if action:
        stmt = stmt.where(Transaction.action == action)
    result = await session.execute(stmt)
    return result.scalar()


async def get_transaction(session, tx_id):
    result = await session.execute(
        select(Transaction).where(Transaction.id == tx_id)
    )
    return result.scalar_one_or_none()


async def delete_transaction(session, tx_id):
    from sqlalchemy import delete as sa_delete
    await session.execute(sa_delete(Transaction).where(Transaction.id == tx_id))
    await session.commit()


# --- Daily Reports ---

async def create_report(session, report_date):
    report = DailyReport(id=str(uuid.uuid4()), report_date=report_date, status="pending")
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return report


async def get_report_by_date(session, report_date):
    result = await session.execute(
        select(DailyReport).where(DailyReport.report_date == report_date)
    )
    return result.scalar_one_or_none()


async def get_report_by_id(session, report_id):
    result = await session.execute(
        select(DailyReport).where(DailyReport.id == report_id)
    )
    return result.scalar_one_or_none()


async def get_recent_reports(session, limit=30):
    result = await session.execute(
        select(DailyReport).order_by(DailyReport.report_date.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def update_report(session, report_id, **kwargs):
    from sqlalchemy import update as sa_update
    await session.execute(
        sa_update(DailyReport).where(DailyReport.id == report_id).values(**kwargs)
    )
    await session.commit()


async def save_report_section(session, report_id, section_type, content, section_order=0, stock_code=None, status="success"):
    section = ReportSection(
        report_id=report_id, section_type=section_type,
        stock_code=stock_code, content=content,
        section_order=section_order, status=status
    )
    session.add(section)
    await session.commit()
    await session.refresh(section)
    return section


async def get_report_sections(session, report_id):
    result = await session.execute(
        select(ReportSection)
        .where(ReportSection.report_id == report_id)
        .order_by(ReportSection.section_order.asc())
    )
    return list(result.scalars().all())


async def delete_report_sections(session, report_id):
    from sqlalchemy import delete as sa_delete
    await session.execute(
        sa_delete(ReportSection).where(ReportSection.report_id == report_id)
    )
    await session.commit()


# --- Report Contexts (cross-day memory) ---

async def save_report_context(session, report_id, stock_code, advice_type, key_price=None, advice_text=None):
    ctx = ReportContext(
        report_id=report_id, stock_code=stock_code,
        advice_type=advice_type, key_price=key_price,
        advice_text=advice_text, executed=False
    )
    session.add(ctx)
    await session.commit()
    await session.refresh(ctx)
    return ctx


async def get_report_contexts(session, report_id):
    result = await session.execute(
        select(ReportContext).where(ReportContext.report_id == report_id)
    )
    return list(result.scalars().all())


async def get_latest_report_contexts(session, stock_code=None):
    """Get the most recent report's contexts for a stock (or all stocks)."""
    latest_report = await session.execute(
        select(DailyReport).order_by(DailyReport.report_date.desc()).limit(1)
    )
    report = latest_report.scalar_one_or_none()
    if not report:
        return []
    stmt = select(ReportContext).where(ReportContext.report_id == report.id)
    if stock_code:
        stmt = stmt.where(ReportContext.stock_code == stock_code)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_report_context(session, ctx_id, executed, execution_result=None):
    from sqlalchemy import update as sa_update
    await session.execute(
        sa_update(ReportContext).where(ReportContext.id == ctx_id)
        .values(executed=executed, execution_result=execution_result)
    )
    await session.commit()
