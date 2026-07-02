"""Data Engine: cache-first fetch orchestration."""
import logging
from datetime import date
from app.db.database import get_session_factory
from app.db import queries
from app.datasources import get_source_for_market, get_healthy_sources, get_sources

logger = logging.getLogger(__name__)


class DataEngine:
    """Orchestrates data fetching with SQLite caching."""

    async def get_klines(
        self, code: str, period: str, start: str, end: str,
    ) -> tuple[list[dict], str | None]:
        factory = get_session_factory()
        async with factory() as session:
            cached = await queries.get_daily_klines(session, code, start, end)
            if cached and len(cached) > 0:
                return cached, None

            market = self._market_from_code(code)
            source = get_source_for_market(market)
            if source is None:
                return [], f"No datasource for market: {market}"

            try:
                bars = await source.fetch_kline(code, period, start, end)
                if not bars:
                    return [], None

                bar_dicts = [
                    {
                        "trade_date": date.fromisoformat(b.date),
                        "open": b.open, "high": b.high, "low": b.low,
                        "close": b.close, "volume": b.volume, "amount": b.amount,
                    }
                    for b in bars
                ]
                await queries.upsert_daily_klines(session, code, bar_dicts)
                await session.commit()

                return [
                    {
                        "date": b.date,
                        "open": b.open, "high": b.high, "low": b.low,
                        "close": b.close, "volume": b.volume, "amount": b.amount,
                    }
                    for b in bars
                ], None
            except Exception as e:
                logger.error(f"Failed to fetch klines for {code}: {e}")
                return [], f"Data source temporarily unavailable for {code}"

    async def get_realtime(self, code: str) -> tuple[dict | None, str | None]:
        market = self._market_from_code(code)
        source = get_source_for_market(market)
        if source is None:
            return None, f"No datasource for market: {market}"

        try:
            quote = await source.fetch_realtime(code)
            if quote is None:
                return None, None
            return {
                "code": quote.code, "name": quote.name,
                "price": quote.price, "change_pct": quote.change_pct,
                "volume": quote.volume, "high": quote.high,
                "low": quote.low, "timestamp": quote.timestamp,
            }, None
        except Exception as e:
            logger.error(f"Failed to fetch realtime for {code}: {e}")
            return None, f"Data source temporarily unavailable"

    async def get_financial(self, code: str) -> tuple[dict | None, str | None]:
        factory = get_session_factory()
        async with factory() as session:
            cached = await queries.get_latest_financial(session, code)
            if cached:
                return cached, None

            market = self._market_from_code(code)
            source = get_source_for_market(market)
            if source is None:
                return None, f"No datasource for market: {market}"

            try:
                report = await source.fetch_financials(code)
                if report is None:
                    return None, None

                report_dict = {
                    "report_date": report.report_date,
                    "revenue": report.revenue,
                    "net_profit": report.net_profit,
                    "pe_ratio": report.pe_ratio,
                    "pb_ratio": report.pb_ratio,
                    "roe": report.roe,
                    "debt_ratio": report.debt_ratio,
                    "total_assets": report.total_assets,
                    "total_equity": report.total_equity,
                }
                await queries.upsert_financials(session, code, report_dict)
                await session.commit()
                return report_dict, None
            except Exception as e:
                logger.error(f"Failed to fetch financials for {code}: {e}")
                return None, f"Data source temporarily unavailable"

    async def get_index(self, codes: list[str]) -> tuple[list[dict], str | None]:
        results = []
        warnings = []
        for code in codes:
            data, warn = await self.get_realtime(code)
            if data:
                results.append(data)
            if warn:
                warnings.append(warn)
        return results, "; ".join(warnings) if warnings else None

    async def search(self, keyword: str) -> tuple[list[dict], str | None]:
        factory = get_session_factory()
        async with factory() as session:
            db_results = await queries.search_stocks_db(session, keyword)
            if db_results:
                return db_results, None

        all_results = []
        from app.datasources import get_sources
        for source in get_sources().values():
            try:
                stocks = await source.search_stocks(keyword)
                for s in stocks:
                    all_results.append({
                        "code": s.code, "name": s.name,
                        "market": s.market, "industry": s.industry,
                    })
            except Exception as e:
                logger.warning(f"Search failed for source {source.name}: {e}")

        return all_results[:20], None

    async def health(self) -> dict:
        healthy = get_healthy_sources()
        factory = get_session_factory()
        try:
            async with factory() as session:
                from sqlalchemy import text
                await session.execute(text("SELECT 1"))
                db_status = "connected"
        except Exception:
            db_status = "disconnected"

        return {
            "status": "ok" if healthy and db_status == "connected" else "degraded",
            "datasources": {
                name: "healthy" if name in healthy else "unhealthy"
                for name in get_sources()
            },
            "database": db_status,
        }

    @staticmethod
    def _market_from_code(code: str) -> str:
        if code.startswith("us."):
            return "us"
        return "a_share"


engine = DataEngine()
