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


def test_news_refresh_returns_200(client, stock_code):
    r = client.get(f"/api/v1/news/stock/{stock_code}?refresh=true")
    assert r.status_code == 200
    assert "news" in r.json()


def test_news_analyze_endpoint(client, stock_code):
    r = client.post(f"/api/v1/news/stock/{stock_code}/analyze", json={
        "title": "测试新闻标题",
        "source": "东方财富",
        "summary": "测试摘要",
    })
    assert r.status_code == 200
    body = r.text
    assert "data:" in body
    lines = [l for l in body.split("\n") if l.startswith("data: ")]
    assert len(lines) > 0
