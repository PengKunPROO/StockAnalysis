def compute_boll(klines: list[dict], period=20, std_mult=2) -> list[dict]:
    closes = [k["close"] for k in klines]
    result = []
    for i in range(len(closes)):
        if i < period - 1:
            result.append({"upper": None, "mid": None, "lower": None})
        else:
            window = closes[i - period + 1:i + 1]
            mid = sum(window) / period
            variance = sum((x - mid) ** 2 for x in window) / period
            std = variance ** 0.5
            result.append({
                "upper": round(mid + std_mult * std, 4),
                "mid": round(mid, 4),
                "lower": round(mid - std_mult * std, 4),
            })
    return result
