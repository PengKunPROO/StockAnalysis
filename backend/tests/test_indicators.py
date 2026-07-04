def test_indicators_ok(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/indicators?days=60")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) > 0


def test_indicators_has_all(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/indicators?days=60")
    last = r.json()["data"][-1]
    for key in ["macd", "rsi", "kdj", "boll"]:
        assert key in last, f"Missing: {key}"


def test_indicators_days_param(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/indicators?days=30")
    assert r.status_code == 200
    assert len(r.json()["data"]) <= 30
