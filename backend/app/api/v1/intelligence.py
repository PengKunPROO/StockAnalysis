"""市场情报 (intelligence) API: overview dashboard + 6 tabs.

数据源全部使用同花顺 Financial-API (已实测可达)，北向资金保留 eastmoney (kamt 可达)。
所有端点优雅降级：失败返回空 + warning，HTTP 恒 200。
"""
import asyncio
from fastapi import APIRouter, Query
from app.datasources import get_source_for_market
from app.datasources import eastmoney

router = APIRouter(prefix="/intelligence", tags=["intelligence"])

# 5 个核心指数 (fuyao thscode 格式)
INDEX_CODES = {
    "上证指数": "000001.SH",
    "深证成指": "399001.SZ",
    "创业板指": "399006.SZ",
    "科创50": "000688.SH",
    "沪深300": "000300.SH",
}


def _get_source():
    return get_source_for_market("a_share")


@router.get("/overview")
async def overview():
    """市场总览仪表盘: 指数 + 涨跌广度 + 涨停 + 情绪。并行拉取。"""
    source = _get_source()
    if source is None:
        return {"indices": [], "breadth": {}, "warning": "无 A 股数据源"}

    # 并行: 指数快照 + 全市场快照(广度) + 涨停池
    idx_task = source.fetch_index_snapshot(list(INDEX_CODES.values()))
    snap_task = source.fetch_market_snapshot(limit=2000)
    pool_task = source.fetch_limit_up_pool()
    idx_raw, snapshot, pool = await asyncio.gather(idx_task, snap_task, pool_task)

    warnings = []
    indices = []
    for name, thscode in INDEX_CODES.items():
        match = next((i for i in idx_raw if i.get("code") == _to_our(thscode)), None)
        if match:
            indices.append({"name": name, "code": match["code"], **{k: v for k, v in match.items() if k != "name"}})

    # 涨跌广度
    breadth = {"up": 0, "down": 0, "flat": 0, "limit_up": 0, "limit_down": 0}
    for s in snapshot:
        chg = s.get("change_pct")
        if chg is None:
            continue
        if chg > 0.01:
            breadth["up"] += 1
        elif chg < -0.01:
            breadth["down"] += 1
        else:
            breadth["flat"] += 1
        if chg >= 9.8:
            breadth["limit_up"] += 1
        elif chg <= -9.8:
            breadth["limit_down"] += 1
    if not snapshot:
        warnings.append("行情快照不可用")

    # 涨停分桶 + 情绪
    board_buckets = {}
    promotion_rate = None
    if pool:
        multi = sum(1 for p in pool if (p.get("consecutive_days") or 1) >= 2)
        promotion_rate = round(multi / len(pool) * 100, 1) if pool else 0
        for p in pool:
            d = p.get("consecutive_days") or 1
            bucket = "高位板" if d >= 5 else f"{d}板"
            board_buckets[bucket] = board_buckets.get(bucket, 0) + 1

    total_stocks = breadth["up"] + breadth["down"]
    red_ratio = round(breadth["up"] / total_stocks * 100, 1) if total_stocks else 50
    avg_idx_chg = (sum(i.get("change_pct", 0) for i in indices) / len(indices)) if indices else 0
    fear_greed = max(0, min(100, round(50 + avg_idx_chg * 8 + (red_ratio - 50) * 0.4)))

    result = {
        "indices": indices,
        "breadth": breadth,
        "red_ratio": red_ratio,
        "limit_up_count": len(pool),
        "board_buckets": board_buckets,
        "sentiment": {
            "fear_greed": fear_greed,
            "fear_greed_label": "贪婪" if fear_greed >= 65 else ("恐惧" if fear_greed <= 35 else "中性"),
            "profit_effect": red_ratio,
            "seal_success_rate": None,  # fuyao 涨停池无炸板字段
            "promotion_rate": promotion_rate,
        },
    }
    if warnings:
        result["warning"] = "; ".join(warnings)
    return result


def _to_our(thscode: str) -> str:
    parts = thscode.split(".")
    if len(parts) != 2:
        return thscode
    market = "sh" if parts[1] == "SH" else "sz"
    return f"{market}.{parts[0]}"


@router.get("/limit-up")
async def limit_up():
    source = _get_source()
    if source is None:
        return {"stocks": [], "buckets": {}, "warning": "无数据源"}
    pool, ladder = await asyncio.gather(source.fetch_limit_up_pool(), source.fetch_limit_up_ladder())
    if not pool:
        return {"stocks": [], "buckets": {}, "ladder": ladder, "warning": "涨停股池当日暂无数据"}
    pool.sort(key=lambda p: p.get("consecutive_days") or 1, reverse=True)
    buckets = {}
    for p in pool:
        d = p.get("consecutive_days") or 1
        bucket = "高位板" if d >= 5 else f"{d}板"
        buckets[bucket] = buckets.get(bucket, 0) + 1
    return {"stocks": pool, "buckets": buckets, "ladder": ladder, "count": len(pool)}


@router.get("/fund-flow")
async def fund_flow(scope: str = Query("stock", pattern=r"^(north|stock)$")):
    """资金流: north(北向,eastmoney kamt) / stock(成交额排行,fuyao snapshot)。
    行业/概念资金流: 同花顺无接口，已移除(原 push2 不可达)。"""
    if scope == "north":
        data = await eastmoney.fetch_north_bound(days=10)
        if not data:
            return {"north": [], "warning": "北向资金数据暂不可用"}
        return {"north": data}
    # stock: 成交额排行
    source = _get_source()
    if source is None:
        return {"stocks": [], "warning": "无数据源"}
    snap = await source.fetch_market_snapshot(limit=500)
    if not snap:
        return {"stocks": [], "warning": "行情数据暂不可用"}
    snap.sort(key=lambda s: s.get("amount") or 0, reverse=True)
    top = [
        {"code": s["code"], "name": s.get("name", ""), "amount": s.get("amount"),
         "change_pct": s.get("change_pct")}
        for s in snap[:30]
    ]
    return {"stocks": top, "scope": "stock"}


@router.get("/sectors")
async def sectors():
    """板块轮动: 同花顺 Financial-API 无行业板块接口，诚实降级。"""
    return {"sectors": [], "warning": "同花顺暂未提供行业/概念板块排行接口（原 eastmoney push2 不可达）"}


@router.get("/dragon-tiger")
async def dragon_tiger(date: str = Query("")):
    source = _get_source()
    if source is None:
        return {"stocks": [], "warning": "无数据源"}
    data = await source.fetch_dragon_tiger(date or "", board_type="all")
    if not data:
        return {"stocks": [], "warning": "龙虎榜当日暂无数据（可能盘后才有）"}
    return {"stocks": data, "count": len(data)}


@router.get("/anomalies")
async def anomalies(limit: int = Query(50, ge=5, le=200)):
    source = _get_source()
    if source is None:
        return {"anomalies": [], "warning": "无数据源"}
    data = await source.fetch_anomaly_list()
    if not data:
        return {"anomalies": [], "warning": "异动数据为盘后实时数据，交易时段内才有"}
    out = [
        {"code": a.get("code"), "name": a.get("name"), "change_pct": None,
         "type": a.get("tag") or "异动", "reason": a.get("content"),
         "keywords": a.get("keywords", [])}
        for a in data[:limit]
    ]
    return {"anomalies": out, "count": len(data)}


@router.get("/announcements")
async def announcements(limit: int = Query(20, ge=5, le=100)):
    """热点流: 用同花顺热股榜(总有数据)。异动事件流见 anomalies。"""
    source = _get_source()
    if source is None:
        return {"announcements": [], "warning": "无数据源"}
    data = await source.fetch_hot_stock(level="day")
    if not data:
        return {"announcements": [], "warning": "热点数据暂不可用"}
    out = [
        {"stock": a.get("name", ""), "code": a.get("code", ""),
         "title": f"热股榜 排名#{int(a.get('rank') or 0)}", "date": "", "tag": "热点",
         "heat": a.get("heat")}
        for a in data[:limit]
    ]
    return {"announcements": out, "count": len(data)}
