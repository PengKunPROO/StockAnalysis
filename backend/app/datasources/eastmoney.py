"""East Money supplementary crawler (精简版).

实测仅 `kamt.kline`（北向资金）端点在此环境可达。
其余 push2 clist/push2ex/datacenter/anno 端点不可达，对应功能已改用
同花顺 Financial-API（见 tonghuashun.py）。本模块仅保留北向资金。
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
