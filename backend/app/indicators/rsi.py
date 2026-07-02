def compute_rsi(klines: list[dict], period=14) -> list[dict]:
    closes = [k["close"] for k in klines]
    result = []
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    for i in range(len(closes)):
        if i < period:
            result.append({"rsi14": None})
        else:
            avg_gain = sum(gains[i - period:i]) / period
            avg_loss = sum(losses[i - period:i]) / period
            if avg_loss == 0:
                result.append({"rsi14": 100.0})
            else:
                rs = avg_gain / avg_loss
                result.append({"rsi14": round(100 - 100 / (1 + rs), 2)})
    return result
