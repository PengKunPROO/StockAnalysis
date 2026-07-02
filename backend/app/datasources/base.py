from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class KlineBar:
    """Single OHLCV bar."""
    date: str           # "2026-07-01"
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float


@dataclass
class RealtimeQuote:
    """Latest quote snapshot."""
    code: str
    name: str
    price: float
    change_pct: float
    volume: int
    high: float
    low: float
    timestamp: str      # ISO 8601


@dataclass
class StockInfo:
    """Basic stock identification."""
    code: str           # sh.600519 / us.AAPL
    name: str
    market: str         # "a_share" / "us"
    industry: str


@dataclass
class FinancialReport:
    """Latest financial metrics from a report period."""
    code: str
    report_date: str    # "2026-03-31"
    revenue: float | None = None
    net_profit: float | None = None
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    roe: float | None = None
    debt_ratio: float | None = None
    total_assets: float | None = None
    total_equity: float | None = None


@runtime_checkable
class DataSourceProtocol(Protocol):
    """Interface every datasource plugin must satisfy."""

    @property
    def name(self) -> str: ...

    @property
    def markets(self) -> list[str]: ...

    async def search_stocks(self, keyword: str) -> list[StockInfo]: ...

    async def fetch_kline(
        self, code: str, period: str, start: str, end: str
    ) -> list[KlineBar]: ...

    async def fetch_realtime(self, code: str) -> RealtimeQuote | None: ...

    async def fetch_financials(self, code: str) -> FinancialReport | None: ...

    async def fetch_index(self, code: str) -> RealtimeQuote | None: ...

    def health_check(self) -> bool: ...
