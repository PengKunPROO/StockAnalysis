"""A-share datasource via akshare."""
from datetime import datetime
import akshare as ak
from app.datasources.base import (
    DataSourceProtocol, KlineBar, RealtimeQuote, StockInfo, FinancialReport, NewsArticle,
)


class AShareSource:
    """A-share (沪深) datasource using akshare."""

    @property
    def name(self) -> str:
        return "akshare"

    @property
    def markets(self) -> list[str]:
        return ["a_share"]

    async def search_stocks(self, keyword: str) -> list[StockInfo]:
        import asyncio
        loop = asyncio.get_event_loop()

        def _search():
            try:
                df = ak.stock_info_a_code_name()
                matches = df[
                    df["code"].str.contains(keyword) |
                    df["name"].str.contains(keyword)
                ]
                results = []
                for _, row in matches.head(20).iterrows():
                    raw_code = str(row["code"])
                    if raw_code.startswith("6"):
                        code = f"sh.{raw_code}"
                    else:
                        code = f"sz.{raw_code}"
                    results.append(StockInfo(
                        code=code, name=row["name"],
                        market="a_share", industry="",
                    ))
                return results
            except Exception:
                return []

        return await loop.run_in_executor(None, _search)

    async def fetch_kline(
        self, code: str, period: str = "daily",
        start: str = "2020-01-01", end: str | None = None,
    ) -> list[KlineBar]:
        import asyncio
        loop = asyncio.get_event_loop()

        if end is None:
            end = datetime.now().strftime("%Y%m%d")

        raw_code = code.split(".")[-1]

        def _fetch():
            try:
                if period == "daily":
                    df = ak.stock_zh_a_hist(
                        symbol=raw_code, period="daily",
                        start_date=start.replace("-", ""),
                        end_date=end.replace("-", ""),
                        adjust="qfq",
                    )
                elif period in ("weekly", "monthly"):
                    df = ak.stock_zh_a_hist(
                        symbol=raw_code, period=period,
                        start_date=start.replace("-", ""),
                        end_date=end.replace("-", ""),
                        adjust="qfq",
                    )
                else:
                    return []

                bars = []
                for _, row in df.iterrows():
                    bars.append(KlineBar(
                        date=str(row["日期"])[:10],
                        open=float(row["开盘"]),
                        high=float(row["最高"]),
                        low=float(row["最低"]),
                        close=float(row["收盘"]),
                        volume=int(row["成交量"]),
                        amount=float(row["成交额"]),
                    ))
                return bars
            except Exception:
                return []

        return await loop.run_in_executor(None, _fetch)

    async def fetch_realtime(self, code: str) -> RealtimeQuote | None:
        import asyncio
        loop = asyncio.get_event_loop()
        raw_code = code.split(".")[-1]

        def _fetch():
            try:
                df = ak.stock_zh_a_spot_em()
                row = df[df["代码"] == raw_code]
                if row.empty:
                    return None
                r = row.iloc[0]
                return RealtimeQuote(
                    code=code, name=str(r["名称"]),
                    price=float(r["最新价"]),
                    change_pct=float(r["涨跌幅"]),
                    volume=int(r["成交量"]),
                    high=float(r["最高"]), low=float(r["最低"]),
                    timestamp=datetime.now().isoformat(),
                )
            except Exception:
                return None

        return await loop.run_in_executor(None, _fetch)

    async def fetch_financials(self, code: str) -> FinancialReport | None:
        import asyncio
        loop = asyncio.get_event_loop()
        raw_code = code.split(".")[-1]

        def _fetch():
            try:
                df = ak.stock_financial_abstract_ths(symbol=raw_code, indicator="按报告期")
                if df.empty:
                    return None
                latest = df.iloc[0]
                return FinancialReport(
                    code=code,
                    report_date=str(latest["报告期"]),
                    revenue=_safe_float(latest.get("营业总收入")),
                    net_profit=_safe_float(latest.get("净利润")),
                    pe_ratio=None, pb_ratio=None,
                    roe=_safe_float(latest.get("净资产收益率")),
                    debt_ratio=_safe_float(latest.get("资产负债率")),
                    total_assets=_safe_float(latest.get("资产总计")),
                    total_equity=_safe_float(latest.get("股东权益合计")),
                )
            except Exception:
                return None

        return await loop.run_in_executor(None, _fetch)

    async def fetch_index(self, code: str) -> RealtimeQuote | None:
        import asyncio
        loop = asyncio.get_event_loop()
        raw_code = code.split(".")[-1]

        def _fetch():
            try:
                df = ak.stock_zh_index_spot_em()
                row = df[df["代码"] == raw_code]
                if row.empty:
                    return None
                r = row.iloc[0]
                return RealtimeQuote(
                    code=code, name=str(r["名称"]),
                    price=float(r["最新价"]),
                    change_pct=float(r["涨跌幅"]),
                    volume=int(r["成交量"]) if r.get("成交量") else 0,
                    high=float(r["最高"]), low=float(r["最低"]),
                    timestamp=datetime.now().isoformat(),
                )
            except Exception:
                return None

        return await loop.run_in_executor(None, _fetch)

    async def fetch_news(self, code: str, limit: int = 20) -> list[NewsArticle]:
        import asyncio
        loop = asyncio.get_event_loop()
        raw_code = code.split(".", 1)[1]

        def _fetch():
            try:
                df = ak.stock_news_em(symbol=raw_code)
                # Columns: 关键词, 新闻标题, 新闻内容, 发布时间, 文章来源, 新闻链接
                col_title = df.columns[1]
                col_content = df.columns[2]
                col_time = df.columns[3]
                col_source = df.columns[4]
                col_url = df.columns[5]

                articles = []
                for _, row in df.head(limit).iterrows():
                    articles.append(NewsArticle(
                        title=str(row[col_title]),
                        source=str(row[col_source]),
                        url=str(row[col_url]),
                        summary=str(row[col_content])[:500] if row[col_content] else "",
                        published_at=str(row[col_time]),
                    ))
                return articles
            except Exception:
                return []

        return await loop.run_in_executor(None, _fetch)

    def health_check(self) -> bool:
        try:
            ak.stock_info_a_code_name()
            return True
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
