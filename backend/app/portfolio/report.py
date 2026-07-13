# backend/app/portfolio/report.py
"""Report generation orchestrator - coordinates the 3-stage pipeline."""
import json
import logging
from datetime import date, timedelta
from app.db.database import get_session_factory
from app.db import queries
from app.portfolio.calculator import calculate_portfolio_metrics
from app.portfolio.analyzer import analyze_stock, generate_summary
from app.engine.data_engine import engine as data_engine

logger = logging.getLogger(__name__)


async def generate_report(report_date: date) -> dict:
    """Generate daily report. Returns dict with report metadata and sections.

    Stages:
    1. Portfolio rules (calculator)
    2. Per-stock DeepSeek analysis (parallel)
    3. DeepSeek summary
    """
    factory = get_session_factory()

    # Get holdings + transactions
    async with factory() as session:
        holdings_orm = await queries.get_holdings(session, only_open=True)
        holdings = [
            {
                "code": h.code, "name": h.name, "shares": h.shares,
                "avg_cost": float(h.avg_cost), "buy_date": str(h.buy_date) if h.buy_date else None,
                "id": h.id,
            }
            for h in holdings_orm
        ]
        transactions_orm = await queries.get_transactions(session, limit=200)
        transactions = [
            {
                "code": t.code, "action": t.action, "shares": t.shares,
                "price": float(t.price), "traded_at": str(t.traded_at),
            }
            for t in transactions_orm
        ]

    # Fetch realtime prices for all holdings
    realtime_prices = {}
    for h in holdings:
        try:
            rt, _ = await data_engine.get_realtime(h["code"])
            if rt:
                realtime_prices[h["code"]] = {"price": rt.get("price", h["avg_cost"]), "change_pct": rt.get("change_pct", 0)}
        except Exception:
            realtime_prices[h["code"]] = {"price": h["avg_cost"], "change_pct": 0}

    # Get previous report's contexts (cross-day memory)
    prev_report_date = report_date - timedelta(days=1)
    async with factory() as session:
        prev_report = await queries.get_report_by_date(session, prev_report_date)
        prev_contexts = []
        if prev_report:
            prev_contexts = await queries.get_report_contexts(session, prev_report.id)

    # === Stage 1: Portfolio rules ===
    portfolio_analysis = calculate_portfolio_metrics(holdings, transactions, realtime_prices)

    # Create or get report record
    async with factory() as session:
        existing = await queries.get_report_by_date(session, report_date)
        if existing:
            # Idempotent: delete old sections
            await queries.delete_report_sections(session, existing.id)
            report = existing
            await queries.update_report(session, report.id, status="running")
        else:
            report = await queries.create_report(session, report_date)

        # Save portfolio analysis section
        await queries.save_report_section(
            session, report.id, "portfolio_analysis",
            json.dumps(portfolio_analysis, ensure_ascii=False), 0
        )

    # === Stage 2: Per-stock analysis (parallel) ===
    stock_analyses = []
    prev_by_code = {c.stock_code: c for c in prev_contexts}

    for h in holdings:
        holding_ctx = {
            "shares": h["shares"],
            "avg_cost": h["avg_cost"],
            "weight": next((w["weight"] for w in portfolio_analysis["position_weights"] if w["code"] == h["code"]), 0),
            "pnl": 0,
            "pnl_pct": 0,
        }
        # Calculate pnl from portfolio analysis
        rt = realtime_prices.get(h["code"], {})
        price = rt.get("price", h["avg_cost"])
        holding_ctx["pnl"] = (price - h["avg_cost"]) * h["shares"]
        holding_ctx["pnl_pct"] = ((price - h["avg_cost"]) / h["avg_cost"] * 100) if h["avg_cost"] > 0 else 0

        prev_advice = None
        if h["code"] in prev_by_code:
            c = prev_by_code[h["code"]]
            prev_advice = {
                "advice_type": c.advice_type,
                "advice_text": c.advice_text,
                "key_price": float(c.key_price) if c.key_price else None,
                "executed": c.executed,
            }

        result = await analyze_stock(h["code"], h["name"], holding_ctx, prev_advice)
        result["code"] = h["code"]
        result["name"] = h["name"]
        stock_analyses.append(result)

    # Save stock analysis sections
    async with factory() as session:
        for i, sa in enumerate(stock_analyses):
            status = sa.get("status", "failed")
            await queries.save_report_section(
                session, report.id, "stock_analysis",
                json.dumps(sa, ensure_ascii=False), i + 1,
                stock_code=sa.get("code"), status=status
            )

    # === Stage 3: Summary ===
    summary = await generate_summary(portfolio_analysis, stock_analyses, prev_contexts)

    # Save action plan section + summary
    async with factory() as session:
        await queries.save_report_section(
            session, report.id, "action_plan",
            summary, len(stock_analyses) + 1
        )

        # Save report contexts for cross-day memory
        for sa in stock_analyses:
            if sa.get("status") == "success":
                advice_type = sa.get("advice", "hold")
                key_price = sa.get("stop_loss") or sa.get("target")
                advice_text = sa.get("analysis", "")[:500]
                await queries.save_report_context(
                    session, report.id, sa["code"],
                    advice_type, key_price, advice_text
                )

        # Update report with results
        await queries.update_report(
            session, report.id,
            status="completed",
            total_market_value=portfolio_analysis["total_market_value"],
            total_cost=portfolio_analysis["total_cost"],
            total_pnl=portfolio_analysis["total_pnl"],
            pnl_pct=portfolio_analysis["pnl_pct"],
            summary=summary,
        )

    # Build response
    async with factory() as session:
        sections = await queries.get_report_sections(session, report.id)
        contexts = await queries.get_report_contexts(session, report.id)

    return {
        "report_id": report.id,
        "report_date": str(report_date),
        "status": "completed",
        "total_market_value": portfolio_analysis["total_market_value"],
        "total_cost": portfolio_analysis["total_cost"],
        "total_pnl": portfolio_analysis["total_pnl"],
        "pnl_pct": portfolio_analysis["pnl_pct"],
        "sections": {
            "portfolio_analysis": json.loads(
                next(s.content for s in sections if s.section_type == "portfolio_analysis") or "{}"
            ),
            "stock_analysis": [
                {"stock_code": s.stock_code, "content": json.loads(s.content or "{}"), "status": s.status}
                for s in sections if s.section_type == "stock_analysis"
            ],
            "action_plan": next((s.content for s in sections if s.section_type == "action_plan"), ""),
        },
        "contexts": [
            {
                "id": c.id, "stock_code": c.stock_code,
                "advice_type": c.advice_type, "advice_text": c.advice_text,
                "key_price": float(c.key_price) if c.key_price else None,
                "executed": c.executed, "execution_result": c.execution_result,
            }
            for c in contexts
        ],
    }
