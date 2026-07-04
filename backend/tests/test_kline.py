def test_kline_daily(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/kline?period=daily&start=2026-06-01&end=2026-07-01")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) >= 5, f"Expected >= 5 bars, got {len(data)}"
    bar = data[0]
    assert "date" in bar and "open" in bar and "close" in bar
    assert bar["close"] > 0


def test_kline_cache(client, stock_code):
    r1 = client.get(f"/api/v1/stock/{stock_code}/kline?period=daily&start=2026-06-01&end=2026-07-01")
    assert r1.status_code == 200
    len1 = len(r1.json()["data"])
    r2 = client.get(f"/api/v1/stock/{stock_code}/kline?period=daily&start=2026-06-01&end=2026-07-01")
    assert r2.status_code == 200
    len2 = len(r2.json()["data"])
    assert len2 >= len1
