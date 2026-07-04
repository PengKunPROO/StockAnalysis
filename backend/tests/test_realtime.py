def test_realtime_ok(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/realtime")
    assert r.status_code == 200
    data = r.json()
    assert data["price"] is not None and data["price"] > 0


def test_realtime_fields(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/realtime")
    data = r.json()
    for field in ["price", "change_pct", "volume", "high", "low"]:
        assert field in data, f"Missing field: {field}"


def test_realtime_change_pct_is_number(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/realtime")
    data = r.json()
    assert isinstance(data["change_pct"], (int, float))
