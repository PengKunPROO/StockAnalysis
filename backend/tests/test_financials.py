def test_financials_ok(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/financial")
    assert r.status_code == 200
    data = r.json()
    assert "code" in data


def test_financials_has_report_data(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/financial")
    assert r.status_code == 200


def test_financials_roe_and_debt(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/financial")
    data = r.json()
    reports = data.get("reports", [])
    if reports:
        rpt = reports[0]
        assert "roe" in rpt, "ROE field missing"
        assert "debt_ratio" in rpt, "debt_ratio field missing"
