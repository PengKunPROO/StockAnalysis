"""Technical indicator calculation engine."""
from .macd import compute_macd
from .rsi import compute_rsi
from .kdj import compute_kdj
from .boll import compute_boll


async def compute_all(klines: list[dict]) -> list[dict]:
    """Compute all indicators for a list of kline bars."""
    if not klines:
        return []
    macd = compute_macd(klines)
    rsi = compute_rsi(klines)
    kdj = compute_kdj(klines)
    boll = compute_boll(klines)
    result = []
    for i, k in enumerate(klines):
        result.append({
            "date": k["date"],
            "macd": macd[i] if i < len(macd) else None,
            "rsi": rsi[i] if i < len(rsi) else None,
            "kdj": kdj[i] if i < len(kdj) else None,
            "boll": boll[i] if i < len(boll) else None,
        })
    return result
