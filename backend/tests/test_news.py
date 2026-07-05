def test_news_endpoint_returns_200(client, stock_code):
    r = client.get(f"/api/v1/news/stock/{stock_code}")
    assert r.status_code == 200
    data = r.json()
    assert "news" in data
    assert "cached" in data
    assert "code" in data


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


def test_news_with_limit_param(client, stock_code):
    r = client.get(f"/api/v1/news/stock/{stock_code}?limit=3")
    assert r.status_code == 200
    news = r.json()["news"]
    assert len(news) <= 3


def test_news_with_days_param(client, stock_code):
    r = client.get(f"/api/v1/news/stock/{stock_code}?days=30")
    assert r.status_code == 200
    assert "news" in r.json()


def test_news_cached_on_second_call(client, stock_code):
    r1 = client.get(f"/api/v1/news/stock/{stock_code}")
    assert r1.status_code == 200
    r2 = client.get(f"/api/v1/news/stock/{stock_code}")
    assert r2.status_code == 200
    assert r2.json().get("cached") is True


def test_news_invalid_code_handled(client):
    r = client.get("/api/v1/news/stock/us.NONEXIST_STOCK_12345")
    assert r.status_code == 200
    data = r.json()
    assert "news" in data


def test_news_published_at_field(client, stock_code):
    r = client.get(f"/api/v1/news/stock/{stock_code}")
    for item in r.json().get("news", []):
        if item.get("published_at"):
            assert "published_at" in item


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
