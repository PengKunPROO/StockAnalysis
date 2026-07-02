"""Background sync scheduler using APScheduler."""
import logging
from datetime import date, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.db.database import get_session_factory
from app.db import queries
from app.datasources import get_source_for_market

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def sync_all_daily_klines():
    """Sync latest daily klines for tracked stocks."""
    factory = get_session_factory()
    async with factory() as session:
        codes = await queries.get_all_tracked_codes(session)

    for code in codes:
        market = "a_share" if code.startswith("sh.") or code.startswith("sz.") else "us"
        source = get_source_for_market(market)
        if source is None:
            continue

        try:
            start = str(date.today() - timedelta(days=7))
            end = str(date.today())

            factory2 = get_session_factory()
            async with factory2() as s2:
                max_date = await queries.get_max_trade_date(s2, code)
            if max_date:
                start = str(max_date + timedelta(days=1))

            bars = await source.fetch_kline(code, "daily", start, end)
            if bars:
                bar_dicts = [
                    {
                        "trade_date": b.date,
                        "open": b.open, "high": b.high, "low": b.low,
                        "close": b.close, "volume": b.volume, "amount": b.amount,
                    }
                    for b in bars
                ]
                async with factory2() as s2:
                    await queries.upsert_daily_klines(s2, code, bar_dicts)
                    await queries.log_sync(s2, source.name, "kline", code, "done", len(bar_dicts))
                    await s2.commit()
                logger.info(f"Synced {len(bar_dicts)} bars for {code}")
        except Exception as e:
            logger.error(f"Sync failed for {code}: {e}")


def start_scheduler():
    scheduler.add_job(
        sync_all_daily_klines,
        "cron", hour=16, minute=0,
        id="daily_kline_sync",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Background scheduler started")
