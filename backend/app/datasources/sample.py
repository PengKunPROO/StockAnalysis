"""Sample data source for development when external APIs are unreachable."""
import random
from datetime import date, timedelta
from app.datasources.base import DataSourceProtocol, KlineBar, RealtimeQuote, StockInfo, FinancialReport, NewsArticle


def _generate_klines(code: str, start: str, end: str) -> list[KlineBar]:
    """Generate realistic random kline data."""
    random.seed(hash(code) % 2**31)
    start_d = date.fromisoformat(start)
    end_d = date.fromisoformat(end)

    # Pick base price based on stock type
    if code.startswith("sh.6"):
        base = random.uniform(20, 200)  # Shanghai main board
    elif code.startswith("sz.3"):
        base = random.uniform(15, 80)   # ChiNext
    elif code.startswith("sz.0"):
        base = random.uniform(10, 60)   # Shenzhen
    else:
        base = random.uniform(50, 300)  # US stocks

    price = base * random.uniform(0.7, 1.3)
    bars = []
    current = start_d
    while current <= end_d and current <= date.today():
        if current.weekday() < 5:  # Skip weekends
            change = random.gauss(0, price * 0.02)
            close = max(price + change, price * 0.3)
            open_p = close * random.uniform(0.98, 1.02)
            high = max(open_p, close) * random.uniform(1.0, 1.03)
            low = min(open_p, close) * random.uniform(0.97, 1.0)
            volume = int(random.uniform(5000000, 50000000))
            bars.append(KlineBar(
                date=current.isoformat(),
                open=round(open_p, 2),
                high=round(high, 2),
                low=round(low, 2),
                close=round(close, 2),
                volume=volume,
                amount=round(close * volume, 2),
            ))
            price = close
        current += timedelta(days=1)
    return bars


class SampleSource:
    """Sample data source for development/demo."""

    @property
    def name(self) -> str:
        return "sample"

    @property
    def markets(self) -> list[str]:
        return ["a_share", "us"]

    async def search_stocks(self, keyword: str) -> list[StockInfo]:
        # Use akshare for search (works fine)
        try:
            import akshare as ak
            df = ak.stock_info_a_code_name()
            matches = df[df["code"].str.contains(keyword) | df["name"].str.contains(keyword)]
            results = []
            for _, row in matches.head(10).iterrows():
                raw = str(row["code"])
                code = f"sh.{raw}" if raw.startswith("6") else f"sz.{raw}"
                results.append(StockInfo(code=code, name=row["name"], market="a_share", industry=""))
            return results
        except Exception:
            return []

    async def fetch_kline(self, code: str, period: str = "daily",
                          start: str = "2025-01-01", end: str | None = None) -> list[KlineBar]:
        if end is None:
            end = date.today().isoformat()
        return _generate_klines(code, start, end)

    async def fetch_realtime(self, code: str) -> RealtimeQuote | None:
        bars = _generate_klines(code, "2026-06-01", date.today().isoformat())
        if not bars:
            return None
        last = bars[-1]
        prev = bars[-2] if len(bars) > 1 else last
        change = (last.close - prev.close) / prev.close * 100
        return RealtimeQuote(
            code=code, name=code, price=last.close,
            change_pct=round(change, 2), volume=last.volume,
            high=last.high, low=last.low,
            timestamp=date.today().isoformat(),
        )

    async def fetch_financials(self, code: str) -> FinancialReport | None:
        random.seed(hash(code) % 2**31)
        return FinancialReport(
            code=code,
            report_date="2026-03-31",
            revenue=round(random.uniform(1e9, 5e10), 2),
            net_profit=round(random.uniform(1e8, 1e10), 2),
            pe_ratio=round(random.uniform(10, 60), 1),
            pb_ratio=round(random.uniform(1, 15), 1),
            roe=round(random.uniform(5, 35), 1),
            debt_ratio=round(random.uniform(10, 70), 1),
            total_assets=round(random.uniform(5e9, 1e11), 2),
            total_equity=round(random.uniform(2e9, 5e10), 2),
        )

    async def fetch_index(self, code: str) -> RealtimeQuote | None:
        return await self.fetch_realtime(code)

    async def fetch_news(self, code: str, limit: int = 10) -> list[NewsArticle]:
        import asyncio
        loop = asyncio.get_event_loop()

        def _gen():
            today = date.today().isoformat()
            return [
                NewsArticle(
                    title=f"{code} 发布2026年Q2财报，营收超预期",
                    source="证券时报",
                    url="https://example.com/news/1",
                    summary="公司Q2营收同比增长15%，净利润增长22%，超出市场预期。分析师上调目标价。",
                    published_at=f"{today} 10:30:00",
                ),
                NewsArticle(
                    title=f"{code} 获外资机构大幅增持",
                    source="东方财富",
                    url="https://example.com/news/2",
                    summary="北向资金连续5日净买入，累计增持金额超10亿元。",
                    published_at=f"{today} 09:15:00",
                ),
                NewsArticle(
                    title=f"{code} 股价盘中异动，成交量放大",
                    source="新浪财经",
                    url="https://example.com/news/3",
                    summary="今日开盘后股价快速拉升3%，成交额较前日放大50%。",
                    published_at=f"{today} 11:00:00",
                ),
            ][:limit]

        return await loop.run_in_executor(None, _gen)

    def health_check(self) -> bool:
        return True
