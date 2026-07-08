"""Tonghuashun (同花顺) Financial-API datasource."""
from datetime import datetime, date, timezone, timedelta
import httpx
from app.config import settings
from app.datasources.base import (
    DataSourceProtocol, KlineBar, RealtimeQuote, StockInfo, FinancialReport, NewsArticle,
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
            all_items = []
            offset = 0
            while True:
                data = await self._get("/api/a-share/prices/historical", {
                    "thscode": ths,
                    "interval": interval_map.get(period, "1d"),
                    "start": _date_to_ms(start),
                    "end": _date_to_ms(end),
                    "offset": offset,
                })
                items = data.get("item", [])
                if not items:
                    break
                all_items.extend(items)
                offset += len(items)
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
                for b in all_items
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

    async def fetch_news(self, code: str, limit: int = 10) -> list:
        return []

    # ---- 全市场快照与情报数据 (Financial-API special-data) ----
    # 全部 try/except 降级：失败返回 [] / None，绝不抛异常。
    async def fetch_market_snapshot(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """全市场分页实时行情快照 (prices/snapshot 全市场模式). 不传 thscodes 即全市场."""
        try:
            data = await self._get("/api/a-share/prices/snapshot", {"limit": limit, "offset": offset})
            return [self._parse_quote(it) for it in data.get("item", [])]
        except Exception:
            return []

    async def fetch_limit_up_pool(self, date: str = "") -> list[dict]:
        """涨停股票池 (special-data/limit-up-pool). date=YYYYMMDD 默认今日."""
        if not date:
            from datetime import date as _d
            date = _d.today().strftime("%Y%m%d")
        try:
            data = await self._get("/api/a-share/special-data/limit-up-pool", {
                "date": date, "page": 1, "size": 200,
                "sort_field": "continue_day_cnt", "sort_dir": "desc",
            })
            return [self._parse_limit_up(it) for it in data.get("item", [])]
        except Exception:
            return []

    async def fetch_limit_up_ladder(self) -> list[dict]:
        """连板天梯矩阵 (special-data/limit-up-ladder). 近30交易日 date->boards."""
        try:
            data = await self._get("/api/a-share/special-data/limit-up-ladder", {})
            return data if isinstance(data, list) else []
        except Exception:
            return []

    async def fetch_dragon_tiger(self, date: str = "", board_type: str = "all") -> list[dict]:
        """龙虎榜 (special-data/dragon-tiger-list). date=YYYYMMDD, board_type=all/inst/hot."""
        if not date:
            from datetime import date as _d, timedelta
            date = (_d.today() - timedelta(days=1)).strftime("%Y%m%d")
        try:
            data = await self._get("/api/a-share/special-data/dragon-tiger-list", {
                "trade_date": date, "board_type": board_type, "page": 1, "size": 100,
            })
            items = data.get("stock_items", []) if isinstance(data, dict) else (data or [])
            return [self._parse_dragon_tiger(it) for it in items]
        except Exception:
            return []

    async def fetch_anomaly_list(self, tag: str = "") -> list[dict]:
        """当日个股异动原因列表 (special-data/anomaly-analysis-list)."""
        params = {}
        if tag:
            params["tag"] = tag
        try:
            data = await self._get("/api/a-share/special-data/anomaly-analysis-list", params)
            items = data if isinstance(data, list) else (data.get("item", []) if isinstance(data, dict) else [])
            return [self._parse_anomaly(it) for it in items]
        except Exception:
            return []

    async def fetch_anomaly_stock(self, thscodes: list[str]) -> list[dict]:
        """按股票批量查异动 (special-data/anomaly-analysis-stock). 最多50只."""
        try:
            codes = ",".join([self._to_ths_code(c) for c in thscodes[:50]])
            data = await self._get("/api/a-share/special-data/anomaly-analysis-stock", {"thscodes": codes})
            items = data if isinstance(data, list) else (data.get("item", []) if isinstance(data, dict) else [])
            return [self._parse_anomaly(it) for it in items]
        except Exception:
            return []

    async def fetch_hot_stock(self, level: str = "day") -> list[dict]:
        """热股榜 (special-data/hot-stock-list). level=day/hour."""
        try:
            data = await self._get("/api/a-share/special-data/hot-stock-list", {"level": level})
            return [self._parse_hot(it) for it in data.get("item", [])]
        except Exception:
            return []

    async def fetch_ticker_list(self, asset_type: str = "a-share", limit: int = 5000) -> list[dict]:
        """标的列表 (meta/tickers/list). asset_type=a-share/a-share-index. 用于补全股票名称."""
        try:
            data = await self._get("/api/meta/tickers/list", {"asset_type": asset_type, "limit": limit})
            return [
                {"code": self._to_our_code(it.get("thscode", "")),
                 "name": it.get("name", ""), "exchange": it.get("exchange", "")}
                for it in data.get("item", [])
            ]
        except Exception:
            return []

    async def fetch_index_snapshot(self, thscodes: list[str]) -> list[dict]:
        """指数行情快照 (a-share-index/prices/snapshot)."""
        try:
            data = await self._get("/api/a-share-index/prices/snapshot", {"thscodes": ",".join(thscodes)})
            return [self._parse_quote(it) for it in data.get("item", [])]
        except Exception:
            return []

    # ---- response parsers (snake_case, code normalized to sh.X / sz.X) ----
    def _parse_quote(self, it: dict) -> dict:
        return {
            "code": self._to_our_code(it.get("thscode", "")),
            "name": it.get("name", "") or "",
            "price": _safe_float(it.get("last_price")),
            "change_pct": _safe_float(it.get("price_change_ratio_pct")),
            "volume": _safe_float(it.get("volume")),
            "amount": _safe_float(it.get("turnover")),  # fuyao turnover = 成交额
            "open": _safe_float(it.get("open_price")),
            "high": _safe_float(it.get("high_price")),
            "low": _safe_float(it.get("low_price")),
            "prev_close": _safe_float(it.get("prev_price")),
        }

    def _parse_limit_up(self, it: dict) -> dict:
        return {
            "code": self._to_our_code(it.get("thscode", "")),
            "name": it.get("name", ""),
            "price": _safe_float(it.get("last_price")),
            "change_pct": _safe_float(it.get("price_change_ratio_pct")),
            "limit_up_time": it.get("limit_up_time", ""),
            "reason": it.get("limit_up_reason", ""),
            "consecutive_days": int(it.get("continue_day_cnt") or 1),
            "seal_amount": _safe_float(it.get("seal_money")),
        }

    def _parse_anomaly(self, it: dict) -> dict:
        return {
            "code": self._to_our_code(it.get("thscode", "")),
            "name": it.get("stock_name", it.get("name", "")),
            "content": it.get("analysis_content", ""),
            "keywords": it.get("keyword_list", []),
            "tag": it.get("tag_name", ""),
        }

    def _parse_dragon_tiger(self, it: dict) -> dict:
        return {
            "code": self._to_our_code(it.get("thscode", "")),
            "name": it.get("name", it.get("stock_name", "")),
            "reason": it.get("explain", it.get("reason", "")),
            "change_pct": _safe_float(it.get("price_change_ratio_pct")),
            "net_buy": _safe_float(it.get("net_buy")),
        }

    def _parse_hot(self, it: dict) -> dict:
        return {
            "code": self._to_our_code(it.get("thscode", "")),
            "name": it.get("name", it.get("stock_name", "")),
            "rank": _safe_float(it.get("rank")),
            "heat": _safe_float(it.get("heat")),
        }

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
