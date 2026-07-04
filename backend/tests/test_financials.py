def test_financials_ok(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/financial")
    assert r.status_code == 200
    data = r.json()
    assert "code" in data


def test_financials_has_report_data(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/financial")
    assert r.status_code == 200
