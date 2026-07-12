"""East Money supplementary crawler.

提供:
- 北向资金 (kamt.kline 端点)
- 行业/概念板块排行 (push2 clist 端点)
- 个股公告 (np-anotice-stock 端点)

所有方法优雅降级：失败返回空，绝不抛异常。
"""
import httpx

KAMT = "https://push2.eastmoney.com"


def _num(val):
    try:
        f = float(val)
        return f if f == f and f not in (float("inf"), float("-inf")) else None
    except (TypeError, ValueError):
        return None


async def _get_json(url: str, params: dict, timeout: float = 10.0) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


async def fetch_north_bound(days: int = 10) -> list[dict]:
    """北向资金(沪股通/深股通)净流入历史。kamt 端点可达。"""
    data = await _get_json(f"{KAMT}/api/qt/kamt.kline/get", {
        "fields1": "f1,f2,f3",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
        "klt": "101", "lmt": str(days),
    })
    if not data or data.get("rc") != 0:
        return []
    rows = (data.get("data") or {}).get("s2n") or []
    out = []
    for r in rows:
        if not isinstance(r, list) or len(r) < 4:
            continue
        out.append({
            "date": r[0],
            "sh_connect_net": _num(r[1]),
            "sz_connect_net": _num(r[2]),
            "total_net": _num(r[3]),
        })
    return out


async def fetch_sector_rank(board: str = "industry", limit: int = 30) -> list[dict]:
    """行业/概念板块涨跌幅排行。

    board: "industry" (行业板块) or "concept" (概念板块)
    使用东财 push2 clist 端点。全 try/except 降级。
    """
    fs_map = {
        "industry": "m:90+t:2",
        "concept": "m:90+t:3",
    }
    fs = fs_map.get(board, fs_map["industry"])
    data = await _get_json(f"{KAMT}/api/qt/clist/get", {
        "pn": "1", "pz": str(limit),
        "po": "1", "np": "1",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        "fs": fs,
        "fields": "f2,f3,f4,f8,f12,f14,f104,f128,f140",
    })
    if not data or data.get("rc") != 0:
        return []
    rows = (data.get("data") or {}).get("diff") or []
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        out.append({
            "code": r.get("f12", ""),
            "name": r.get("f14", ""),
            "change_pct": _num(r.get("f3")),
            "amount": _num(r.get("f104")),
            "volume": _num(r.get("f4")),
            "turnover_rate": _num(r.get("f8")),
            "leader_stock": r.get("f128", ""),
        })
    return out


async def fetch_announcements(code: str, limit: int = 20) -> list[dict]:
    """个股公告列表。使用东财 datacenter 端点。全 try/except 降级。"""
    parts = code.split(".")
    if len(parts) != 2:
        return []
    data = await _get_json("https://np-anotice-stock.eastmoney.com/api/security/ann", {
        "sr": "-1",
        "page_size": str(limit),
        "page_index": "1",
        "ann_type": "A",
        "client_source": "web",
        "stock_list": parts[1],
    })
    if not data:
        return []
    rows = (data.get("data") or {}).get("list") or []
    out = []
    for r in rows:
        out.append({
            "title": r.get("title", ""),
            "date": (r.get("notice_date") or "")[:10],
            "type": r.get("ann_type", ""),
            "url": f"https://data.eastmoney.com/notices/detail/{parts[1]}/{r.get('art_code', '')}.html",
        })
    return out


async def fetch_cls_news(code: str, limit: int = 20) -> list[dict]:
    """财联社电报新闻。使用 cls.cn 搜索 API。全 try/except 降级。"""
    parts = code.split(".")
    if len(parts) != 2:
        return []
    raw_code = parts[1]
    # 财联社搜索 API
    data = await _get_json("https://www.cls.cn/api/sw/search", {
        "app": "CailianpressWeb",
        "os": "web",
        "sv": "8.4.6",
        "keyword": raw_code,
    }, timeout=8.0)
    if not data:
        return []
    # 财联社返回结构可能不固定,尝试多种解析路径
    roll_data = (data.get("data") or {}).get("roll_data") or []
    if not roll_data:
        # 尝试另一种结构
        roll_data = (data.get("data") or {}).get("search_result") or []
    out = []
    for r in roll_data[:limit]:
        if not isinstance(r, dict):
            continue
        title = r.get("title") or r.get("content", "")[:80] or ""
        if not title:
            continue
        out.append({
            "title": title,
            "source": "财联社",
            "url": f"https://www.cls.cn/detail/{r.get('id', '')}",
            "summary": (r.get("content") or "")[:500],
            "published_at": (r.get("ctime") or r.get("published_at") or "")[:19] if isinstance(r.get("ctime") or r.get("published_at"), str) else "",
        })
    return out
