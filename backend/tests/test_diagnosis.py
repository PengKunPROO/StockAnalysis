import json
import pytest
from httpx import ASGITransport


@pytest.fixture(scope="module")
def async_client():
    from app.main import app
    transport = ASGITransport(app=app)
    from httpx import AsyncClient
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.skip(reason="requires LLM API key — run manually")
def test_diagnosis_chat_returns_200(client):
    r = client.post("/api/v1/diagnosis/chat", json={
        "skill": "股票分析", "message": "你好",
        "stock_codes": [{"code": "sh.600519", "name": "贵州茅台"}],
    })
    assert r.status_code == 200


@pytest.mark.skip(reason="requires LLM API key — run manually")
def test_diagnosis_has_session_id(client):
    r = client.post("/api/v1/diagnosis/chat", json={
        "skill": "股票分析", "message": "你好",
        "stock_codes": [{"code": "sh.600519", "name": "贵州茅台"}],
    })
    for line in r.text.split("\n"):
        if line.startswith("data: "):
            d = json.loads(line[6:])
            if d.get("session_id"):
                assert len(d["session_id"]) > 10
                return
    assert False, "No session_id in SSE stream"
