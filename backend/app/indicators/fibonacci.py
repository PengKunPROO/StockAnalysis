def compute_fibonacci(klines: list[dict], lookback=60) -> dict | None:
    """Fibonacci retracement levels over the trailing window (latest bar)."""
    window = klines[-lookback:]
    if len(window) < 5:
        return None
    highs = [k["high"] for k in window]
    lows = [k["low"] for k in window]
    high = max(highs)
    low = min(lows)
    rng = high - low
    if rng == 0:
        return None
    current = window[-1]["close"]
    direction = "up" if current >= (high + low) / 2 else "down"
    levels = {}
    for pct in [0.0, 23.6, 38.2, 50.0, 61.8, 78.6]:
        if direction == "up":
            levels[f"{pct}"] = round(high - rng * pct / 100, 4)
        else:
            levels[f"{pct}"] = round(low + rng * pct / 100, 4)
    return {
        "high": round(high, 4),
        "low": round(low, 4),
        "direction": direction,
        "levels": levels,
        "window": len(window),
    }
