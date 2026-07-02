"""Tonghuashun (同花顺) Financial-API datasource."""
from datetime import datetime, date, timedelta
import httpx
from app.config import settings
from app.datasources.base import (
    DataSourceProtocol, KlineBar, RealtimeQuote, StockInfo, FinancialReport,
)

BASE_URL = "https://fuyao.aicubes.cn/api"


class TonghuashunSource:
    """同花顺 Financial-API datasource."""

    def __init__(self):
        self._api_key = ""

    def _get_key(self) -> str:
        if not self._api_key:
            import os
            self._api_key = (
                os.environ.get("FUYAO_API_KEY", "")
                or settings.fuyao_api_key
                or settings.diagnosis_llm_api_key
            )
        return self._api_key

    @property
    def name(self) -> str:
        return "tonghuashun"

    @property
    def markets(self) -> list[str]:
        return ["a_share"]

    async def _get(self, path: str, params: dict = None) -> dict:
        key = self._get_key()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{BASE_URL}{path}",
                params=params or {},
                headers={"X-api-key": key},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                raise Exception(f"API error: {data.get('message', 'unknown')}")
            return data.get("data", {})

    def _to_our_code(self, thscode: str) -> str:
        """Convert 600519.SH → sh.600519"""
        parts = thscode.split(".")
        market = "sh" if parts[1] == "SH" else "sz"
        return f"{market}.{parts[0]}"

    def _to_ths_code(self, our_code: str) -> str:
        """Convert sh.600519 → 600519.SH"""
        parts = our_code.split(".")
        market = "SH" if parts[0] == "sh" else "SZ"
        return f"{parts[1]}.{market}"

    async def search_stocks(self, keyword: str) -> list[StockInfo]:
        try:
            data = await self._get("/a-share/tickers/search", {"q": keyword, "limit": 20})
            items = data.get("items", [])
            return [
                StockInfo(
                    code=self._to_our_code(item["thscode"]),
                    name=item.get("name", ""),
                    market="a_share",
                    industry=item.get("industry", ""),
                )
                for item in items
            ]
        except Exception:
            return []

    async def fetch_kline(
        self, code: str, period: str = "daily",
        start: str = "2020-01-01", end: str | None = None,
    ) -> list[KlineBar]:
        if end is None:
            end = date.today().isoformat()

        try:
            ths = self._to_ths_code(code)
            freq_map = {"daily": "1d", "weekly": "1w", "monthly": "1m"}
            data = await self._get("/a-share/prices/historical", {
                "thscode": ths,
                "freq": freq_map.get(period, "1d"),
                "start_date": start,
                "end_date": end,
                "adjust": "qfq",
            })
            bars = data.get("bars", [])
            return [
                KlineBar(
                    date=b["date"],
                    open=float(b["open"]),
                    high=float(b["high"]),
                    low=float(b["low"]),
                    close=float(b["close"]),
                    volume=int(b.get("volume", 0)),
                    amount=float(b.get("amount", 0)),
                )
                for b in bars
            ]
        except Exception:
            return []

    async def fetch_realtime(self, code: str) -> RealtimeQuote | None:
        try:
            ths = self._to_ths_code(code)
            data = await self._get("/a-share/prices/snapshot", {"thscodes": ths})
            items = data.get("items", [])
            if not items:
                return None
            item = items[0]
            change_pct = float(item.get("change_pct", 0) or 0)
            return RealtimeQuote(
                code=code,
                name=item.get("name", code),
                price=float(item.get("latest", 0)),
                change_pct=round(change_pct, 2),
                volume=int(item.get("volume", 0) or 0),
                high=float(item.get("high", 0) or 0),
                low=float(item.get("low", 0) or 0),
                timestamp=datetime.now().isoformat(),
            )
        except Exception:
            return None

    async def fetch_financials(self, code: str) -> FinancialReport | None:
        try:
            ths = self._to_ths_code(code)
            data = await self._get("/a-share/financials/indicators", {
                "thscode": ths,
                "limit": 1,
            })
            items = data.get("items", [])
            if not items:
                return None
            item = items[0]
            return FinancialReport(
                code=code,
                report_date=item.get("report_date", ""),
                revenue=_safe_float(item.get("revenue")),
                net_profit=_safe_float(item.get("net_profit")),
                pe_ratio=_safe_float(item.get("pe_ttm")),
                pb_ratio=_safe_float(item.get("pb")),
                roe=_safe_float(item.get("roe")),
                debt_ratio=_safe_float(item.get("debt_to_assets")),
                total_assets=_safe_float(item.get("total_assets")),
                total_equity=_safe_float(item.get("total_equity")),
            )
        except Exception:
            return None

    async def fetch_index(self, code: str) -> RealtimeQuote | None:
        try:
            ths = self._to_ths_code(code)
            return await self.fetch_realtime(code) if ths else None
        except Exception:
            return None

    def health_check(self) -> bool:
        return bool(self._get_key())


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
