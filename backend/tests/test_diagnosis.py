import json
import pytest
from httpx import ASGITransport

from app.api.v1.diagnosis import _classify_line


class TestClassifyLine:
    def test_chinese_analysis_is_analysis(self):
        t, c = _classify_line("## 兆易创新技术分析报告")
        assert t == "analysis"
        assert c == "## 兆易创新技术分析报告"

    def test_markdown_table_is_analysis(self):
        t, c = _classify_line("| 指标 | 数值 |")
        assert t == "analysis"

    def test_chinese_list_is_analysis(self):
        t, c = _classify_line("- MACD指标：-54.82，空头排列")
        assert t == "analysis"

    def test_number_with_percent_is_analysis(self):
        t, c = _classify_line("涨跌幅 -2.09%")
        assert t == "analysis"

    def test_curl_command_is_log(self):
        t, c = _classify_line('curl -s --max-time 15 "http://localhost:8002/api/v1/stock/sh.600519/realtime"')
        assert t == "log"
        assert "curl" in c

    def test_file_path_is_log(self):
        t, c = _classify_line("Remote: `git@github.com:PengKunPROO/StockAnalysis.git`")
        assert t == "log"

    def test_project_root_is_log(self):
        t, c = _classify_line("Project root: `D:\\AI\\hermesStockAgent`")
        assert t == "log"

    def test_code_block_delimiter_is_log(self):
        t, c = _classify_line("```python")
        assert t == "log"

    def test_import_statement_is_log(self):
        t, c = _classify_line("import asyncio")
        assert t == "log"

    def test_empty_line_is_skip(self):
        t, c = _classify_line("")
        assert t == "skip"
        assert c is None

    def test_whitespace_only_is_skip(self):
        t, c = _classify_line("   \t  ")
        assert t == "skip"

    def test_session_marker_is_skip(self):
        t, c = _classify_line("Session: 20260715_010356_0e8c45")
        assert t == "skip"

    def test_duration_is_skip(self):
        t, c = _classify_line("Duration: 45.2s")
        assert t == "skip"

    def test_hermes_resume_is_skip(self):
        t, c = _classify_line("hermes --resume 20260715_010356_0e8c45")
        assert t == "skip"

    def test_box_drawing_is_skip(self):
        t, c = _classify_line("╭──────────────────╮")
        assert t == "skip"

    def test_pure_english_heading_is_log(self):
        """English-only ### headings are skill echo, not analysis."""
        t, c = _classify_line("### What NOT to push")
        assert t == "log"

    def test_mixed_chinese_english_is_analysis(self):
        t, c = _classify_line("## 兆易创新 (sh.603986) 综合分析")
        assert t == "analysis"

    def test_mongodb_config_line_is_log(self):
        t, c = _classify_line("name: hermesstockagent-workflow")
        assert t == "log"


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
