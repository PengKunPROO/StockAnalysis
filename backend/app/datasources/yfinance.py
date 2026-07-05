"""US stock datasource via yfinance."""
from datetime import datetime
import yfinance as yf
from app.datasources.base import (
    DataSourceProtocol, KlineBar, RealtimeQuote, StockInfo, FinancialReport, NewsArticle,
)


class USStockSource:
    """US stock datasource using yfinance."""

    @property
    def name(self) -> str:
        return "yfinance"

    @property
    def markets(self) -> list[str]:
        return ["us"]

    async def search_stocks(self, keyword: str) -> list[StockInfo]:
        import asyncio
        loop = asyncio.get_event_loop()

        def _search():
            try:
                ticker = yf.Ticker(keyword.upper())
                info = ticker.info or {}
                if not info:
                    return []
                return [StockInfo(
                    code=f"us.{keyword.upper()}",
                    name=info.get("longName") or info.get("shortName", ""),
                    market="us",
                    industry=info.get("industry", ""),
                )]
            except Exception:
                return []

        return await loop.run_in_executor(None, _search)

    async def fetch_kline(
        self, code: str, period: str = "daily",
        start: str = "2020-01-01", end: str | None = None,
    ) -> list[KlineBar]:
        import asyncio
        loop = asyncio.get_event_loop()

        ticker_symbol = code.split(".")[-1]
        interval_map = {"daily": "1d", "weekly": "1wk", "monthly": "1mo"}
        interval = interval_map.get(period, "1d")

        if end is None:
            end = datetime.now().strftime("%Y-%m-%d")

        def _fetch():
            try:
                ticker = yf.Ticker(ticker_symbol)
                df = ticker.history(start=start, end=end, interval=interval)
                if df.empty:
                    return []
                bars = []
                for idx, row in df.iterrows():
                    bars.append(KlineBar(
                        date=idx.strftime("%Y-%m-%d"),
                        open=float(row["Open"]),
                        high=float(row["High"]),
                        low=float(row["Low"]),
                        close=float(row["Close"]),
                        volume=int(row["Volume"]),
                        amount=float(row["Close"] * row["Volume"]),
                    ))
                return bars
            except Exception:
                return []

        return await loop.run_in_executor(None, _fetch)

    async def fetch_realtime(self, code: str) -> RealtimeQuote | None:
        import asyncio
        loop = asyncio.get_event_loop()
        ticker_symbol = code.split(".")[-1]

        def _fetch():
            try:
                ticker = yf.Ticker(ticker_symbol)
                info = ticker.info or {}
                if not info:
                    return None
                return RealtimeQuote(
                    code=code,
                    name=info.get("shortName", ticker_symbol),
                    price=float(info.get("currentPrice", info.get("regularMarketPrice", 0))),
                    change_pct=float(info.get("regularMarketChangePercent", 0)),
                    volume=int(info.get("volume", 0)),
                    high=float(info.get("dayHigh", 0)),
                    low=float(info.get("dayLow", 0)),
                    timestamp=datetime.now().isoformat(),
                )
            except Exception:
                return None

        return await loop.run_in_executor(None, _fetch)

    async def fetch_financials(self, code: str) -> FinancialReport | None:
        import asyncio
        loop = asyncio.get_event_loop()
        ticker_symbol = code.split(".")[-1]

        def _fetch():
            try:
                ticker = yf.Ticker(ticker_symbol)
                info = ticker.info or {}
                if not info:
                    return None
                return FinancialReport(
                    code=code,
                    report_date=datetime.now().strftime("%Y-%m-%d"),
                    revenue=_safe_float(info.get("totalRevenue")),
                    net_profit=_safe_float(info.get("netIncomeToCommon")),
                    pe_ratio=_safe_float(info.get("trailingPE")),
                    pb_ratio=_safe_float(info.get("priceToBook")),
                    roe=_safe_float(info.get("returnOnEquity")),
                    debt_ratio=_safe_float(info.get("debtToEquity")),
                    total_assets=_safe_float(info.get("totalAssets")),
                    total_equity=_safe_float(info.get("totalStockholderEquity")),
                )
            except Exception:
                return None

        return await loop.run_in_executor(None, _fetch)

    async def fetch_index(self, code: str) -> RealtimeQuote | None:
        import asyncio
        loop = asyncio.get_event_loop()
        ticker_symbol = code.split(".")[-1]

        def _fetch():
            try:
                ticker = yf.Ticker(ticker_symbol)
                info = ticker.info or {}
                if not info:
                    try:
                        fast = ticker.fast_info
                        return RealtimeQuote(
                            code=code, name=ticker_symbol,
                            price=float(fast.get("lastPrice", 0)),
                            change_pct=0.0, volume=0,
                            high=float(fast.get("dayHigh", 0)),
                            low=float(fast.get("dayLow", 0)),
                            timestamp=datetime.now().isoformat(),
                        )
                    except Exception:
                        return None
                return RealtimeQuote(
                    code=code,
                    name=info.get("shortName", ticker_symbol),
                    price=float(info.get("regularMarketPrice", 0)),
                    change_pct=float(info.get("regularMarketChangePercent", 0)),
                    volume=int(info.get("regularMarketVolume", 0)),
                    high=float(info.get("regularMarketDayHigh", 0)),
                    low=float(info.get("regularMarketDayLow", 0)),
                    timestamp=datetime.now().isoformat(),
                )
            except Exception:
                return None

        return await loop.run_in_executor(None, _fetch)

    async def fetch_news(self, code: str, limit: int = 10) -> list[NewsArticle]:
        import asyncio
        loop = asyncio.get_event_loop()
        ticker_symbol = code.split(".", 1)[1]

        def _fetch():
            try:
                ticker = yf.Ticker(ticker_symbol)
                raw_news = ticker.news or []
                articles = []
                for item in raw_news[:limit]:
                    articles.append(NewsArticle(
                        title=item.get("title", ""),
                        source=item.get("publisher", ""),
                        url=item.get("link", ""),
                        summary=item.get("summary", "")[:500],
                        published_at=str(item.get("providerPublishTime", "")),
                    ))
                return articles
            except Exception:
                return []

        return await loop.run_in_executor(None, _fetch)

    def health_check(self) -> bool:
        try:
            ticker = yf.Ticker("AAPL")
            info = ticker.info
            return info is not None and len(info) > 0
        except Exception:
            return False


def _safe_float(val) -> float | None:
    import math
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None
