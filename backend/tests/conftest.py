import os
import pytest
from fastapi.testclient import TestClient

FUYAO_KEY = os.environ.get("FUYAO_API_KEY", "")
HAS_API_KEY = bool(FUYAO_KEY.strip())

needs_api_key = pytest.mark.skipif(
    not HAS_API_KEY,
    reason="FUYAO_API_KEY not set — skipping real data test"
)


@pytest.fixture(scope="module")
def client():
    import asyncio
    from app.main import app
    from app.db.database import init_db
    loop = asyncio.new_event_loop()
    loop.run_until_complete(init_db())
    loop.close()
    return TestClient(app)


@pytest.fixture(scope="module")
def api_key():
    return FUYAO_KEY


@pytest.fixture
def stock_code():
    return "sh.600519"
