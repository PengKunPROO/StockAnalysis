"""Tonghuashun (同花顺) Financial-API datasource."""
from datetime import datetime, date, timezone, timedelta
import httpx
from app.config import settings
from app.datasources.base import (
    DataSourceProtocol, KlineBar, RealtimeQuote, StockInfo, FinancialReport,
)

BASE_URL = "https://fuyao.aicubes.cn"


def _ms_to_date(ms: int) -> str:
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone(timedelta(hours=8)))
    return dt.date().isoformat()


def _date_to_ms(d: str) -> int:
    dt = datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone(timedelta(hours=8)))
    return int(dt.timestamp() * 1000)


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
                raise Exception(f"API error {data.get('code')}: {data.get('message', 'unknown')}")
            return data.get("data", {})

    def _to_our_code(self, thscode: str) -> str:
        parts = thscode.split(".")
        market = "sh" if parts[1] == "SH" else "sz"
        return f"{market}.{parts[0]}"

    def _to_ths_code(self, our_code: str) -> str:
        parts = our_code.split(".")
        market = "SH" if parts[0] == "sh" else "SZ"
        return f"{parts[1]}.{market}"

    async def search_stocks(self, keyword: str) -> list[StockInfo]:
        try:
            data = await self._get("/api/meta/tickers/search", {"q": keyword, "limit": 20})
            items = data.get("item", [])
            return [
                StockInfo(
                    code=self._to_our_code(item["thscode"]),
                    name=item.get("name", ""),
                    market="a_share",
                    industry="",
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
            interval_map = {"daily": "1d", "weekly": "1w", "monthly": "1m"}
            data = await self._get("/api/a-share/prices/historical", {
                "thscode": ths,
                "interval": interval_map.get(period, "1d"),
                "start": _date_to_ms(start),
                "end": _date_to_ms(end),
            })
            items = data.get("item", [])
            return [
                KlineBar(
                    date=_ms_to_date(int(b["date_ms"])),
                    open=float(b["open_price"]),
                    high=float(b["high_price"]),
                    low=float(b["low_price"]),
                    close=float(b["close_price"]),
                    volume=int(float(b.get("volume", 0))),
                    amount=float(b.get("turnover", 0)),
                )
                for b in items
            ]
        except Exception:
            return []

    async def fetch_realtime(self, code: str) -> RealtimeQuote | None:
        try:
            ths = self._to_ths_code(code)
            data = await self._get("/api/a-share/prices/snapshot", {"thscodes": ths})
            items = data.get("item", [])
            if not items:
                return None
            item = items[0]
            prev = item.get("prev_price")
            price = item.get("last_price")
            if price is None:
                price = prev  # fallback to previous close when market is closed
            if price is None:
                price = 0
            return RealtimeQuote(
                code=code,
                name=item.get("thscode", code),
                price=float(price),
                change_pct=round(float(item.get("price_change_ratio_pct") or 0), 2),
                volume=int(float(item.get("volume") or 0)),
                high=float(item.get("high_price") or item.get("prev_price") or 0),
                low=float(item.get("low_price") or item.get("prev_price") or 0),
                timestamp=datetime.now().isoformat(),
            )
        except Exception:
            return None

    async def fetch_financials(self, code: str) -> FinancialReport | None:
        try:
            ths = self._to_ths_code(code)
            today = date.today()
            year = today.year
            quarter = (today.month - 1) // 3 + 1
            # Try latest quarter, fall back to previous
            for q in range(quarter, 0, -1):
                try:
                    data = await self._get("/api/a-share/financials/indicators", {
                        "thscode": ths,
                        "report": f"{year}-{q}",
                        "limit": 1,
                    })
                    break
                except Exception:
                    if q == 1:
                        # Try previous year Q4
                        data = await self._get("/api/a-share/financials/indicators", {
                            "thscode": ths,
                            "report": f"{year - 1}-4",
                            "limit": 1,
                        })
                    continue

            # Extract indicators from nested abilities structure
            indicators = {}
            for ability in data.get("abilities", []):
                for ind in ability.get("indicators", []):
                    indicators[ind["index_id"]] = ind.get("value")

            return FinancialReport(
                code=code,
                report_date=data.get("report", ""),
                revenue=None,  # not in indicators API
                net_profit=None,
                pe_ratio=None,  # not in indicators API
                pb_ratio=None,
                roe=_safe_float(indicators.get("index_weighted_avg_roe")),
                debt_ratio=_safe_float(indicators.get("assets_debt_ratio")),
                total_assets=None,
                total_equity=None,
            )
        except Exception:
            return None

    async def fetch_index(self, code: str) -> RealtimeQuote | None:
        try:
            return await self.fetch_realtime(code)
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
