import json
import pytest
from app.diagnosis.tools import TOOL_DEFINITIONS, execute_tool


def test_tool_definitions_non_empty():
    assert len(TOOL_DEFINITIONS) >= 5


def test_all_tools_have_name_and_description():
    for t in TOOL_DEFINITIONS:
        assert "name" in t["function"]
        assert "description" in t["function"]
        assert len(t["function"]["description"]) > 5


def test_get_news_tool_exists():
    names = [t["function"]["name"] for t in TOOL_DEFINITIONS]
    assert "get_news" in names
    assert "get_kline" in names
    assert "get_indicators" in names
    assert "get_financials" in names
    assert "get_realtime" in names
    assert "search_stocks" in names


@pytest.mark.asyncio
async def test_execute_tool_unknown():
    result = await execute_tool("nonexistent_tool", {})
    data = json.loads(result)
    assert "error" in data


@pytest.mark.asyncio
async def test_execute_tool_search():
    result = await execute_tool("search_stocks", {"keyword": "600519"})
    data = json.loads(result)
    assert isinstance(data, list)
    if data:
        assert "code" in data[0]
        assert "name" in data[0]


@pytest.mark.asyncio
async def test_execute_tool_get_news():
    result = await execute_tool("get_news", {"code": "sh.600519", "limit": 3})
    data = json.loads(result)
    assert isinstance(data, list)
    for item in data:
        assert "title" in item
        assert "source" in item
