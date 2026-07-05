def test_news_endpoint_returns_200(client, stock_code):
    r = client.get(f"/api/v1/news/stock/{stock_code}")
    assert r.status_code == 200
    assert "news" in r.json()


def test_news_structure(client, stock_code):
    r = client.get(f"/api/v1/news/stock/{stock_code}")
    data = r.json()
    for item in data.get("news", []):
        assert "title" in item
        assert "source" in item
