def test_market_index_returns_200(client):
    r = client.get("/api/v1/market/index?codes=sh.000001,sz.399001")
    assert r.status_code == 200
    assert "indices" in r.json()


def test_market_index_has_data(client):
    r = client.get("/api/v1/market/index?codes=sh.000001,sz.399001")
    indices = r.json()["indices"]
    assert len(indices) >= 1
    for i in indices:
        assert "code" in i
        assert "price" in i
        assert "change_pct" in i


def test_market_index_single_code(client):
    r = client.get("/api/v1/market/index?codes=sh.000001")
    assert r.status_code == 200
    assert len(r.json()["indices"]) == 1
