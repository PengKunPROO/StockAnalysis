"""Screener v2 tests - Task 1: FilterField model + factor definitions."""
import pytest
from app.screener.fields import (
    get_fields, matches_snapshot, FIELD_BY_NAME, FIELDS,
    SNAPSHOT_FIELDS, PASS2_FIELDS, TECH_FIELDS, NEWS_FIELDS, SORTABLE,
)


class TestFields:
    def test_field_count(self):
        fl = get_fields()
        assert len(fl) >= 18  # 18+ factors

    def test_all_fields_have_description(self):
        for f in get_fields():
            assert f.description, f"Field {f.name} missing description"

    def test_all_fields_have_source(self):
        for f in get_fields():
            assert f.source, f"Field {f.name} missing source"

    def test_all_fields_have_pass_phase(self):
        for f in get_fields():
            assert f.pass_phase in (1, 2), f"Field {f.name} invalid pass_phase"

    def test_snapshot_fields_available(self):
        # These must be available (fuyao snapshot provides them)
        for name in ["change_pct", "amount", "amplitude", "open", "high", "low"]:
            f = FIELD_BY_NAME[name]
            assert f.available, f"{name} should be available"
            assert f.pass_phase == 1

    def test_valuation_fields_unavailable(self):
        # Eastmoney push2 unreachable -> mark unavailable
        for name in ["pe_ttm", "pb", "total_mv", "turnover_rate"]:
            f = FIELD_BY_NAME[name]
            assert not f.available, f"{name} should be unavailable"
            assert f.pass_phase == 2

    def test_financial_fields_available(self):
        for name in ["roe", "debt_ratio"]:
            f = FIELD_BY_NAME[name]
            assert f.available
            assert f.pass_phase == 2

    def test_tech_fields_available(self):
        for name in ["macd_golden_cross", "rsi_oversold", "boll_breakout", "kdj_golden_cross",
                      "near_high_drop", "change_5d", "change_20d"]:
            assert name in FIELD_BY_NAME, f"{name} not defined"
            assert FIELD_BY_NAME[name].available

    def test_news_fields_available(self):
        for name in ["on_dragon_tiger", "hot_rank", "main_net_flow"]:
            assert name in FIELD_BY_NAME, f"{name} not defined"
            assert FIELD_BY_NAME[name].available
            assert FIELD_BY_NAME[name].pass_phase == 2

    def test_matches_snapshot_change_pct(self):
        stock = {"change_pct": 5.5, "amount": 1000000, "amplitude": 3.2}
        assert matches_snapshot(stock, {"change_pct": {"min": 3}})
        assert not matches_snapshot(stock, {"change_pct": {"min": 6}})

    def test_matches_snapshot_amount(self):
        stock = {"change_pct": 1.0, "amount": 5000000}
        assert matches_snapshot(stock, {"amount": {"min": 1000000}})
        assert not matches_snapshot(stock, {"amount": {"min": 6000000}})

    def test_matches_snapshot_amplitude(self):
        stock = {"change_pct": 1.0, "amplitude": 6.5}
        assert matches_snapshot(stock, {"amplitude": {"min": 5}})
        assert not matches_snapshot(stock, {"amplitude": {"min": 7}})

    def test_matches_snapshot_null_skips_filter(self):
        """When snapshot value is None (non-trading hours), skip filter instead of rejecting."""
        stock = {"change_pct": None, "amount": None}
        assert matches_snapshot(stock, {"change_pct": {"min": 3}})

    def test_sortable_includes_new_fields(self):
        assert "change_pct" in SORTABLE
        assert "amount" in SORTABLE
        assert "amplitude" in SORTABLE
        assert "roe" in SORTABLE

    def test_field_sets_consistency(self):
        """All PASS2 fields should have pass_phase==2, all SNAPSHOT fields pass_phase==1."""
        for name in SNAPSHOT_FIELDS:
            assert FIELD_BY_NAME[name].pass_phase == 1, f"{name} should be pass_phase 1"
        for name in PASS2_FIELDS:
            assert FIELD_BY_NAME[name].pass_phase == 2, f"{name} should be pass_phase 2"

    def test_tech_and_news_sets_disjoint(self):
        assert TECH_FIELDS.isdisjoint(NEWS_FIELDS)

    def test_news_fields_set(self):
        assert NEWS_FIELDS == {"on_dragon_tiger", "hot_rank", "main_net_flow"}


# === Task 2: Engine tests ===

from app.screener.engine import list_skills, run_screener, SKILLS
from unittest.mock import AsyncMock, patch, MagicMock


class TestSkills:
    def test_six_skills(self):
        skills = list_skills()
        assert len(skills) == 6

    def test_skill_names(self):
        skills = list_skills()
        names = [s["name"] for s in skills]
        assert "oversold_bounce" in names
        assert "cigarette_butt" in names
        assert "value" in names
        assert "technical" in names
        assert "news_driven" in names
        assert "breakout" in names

    def test_skill_has_fields(self):
        for s in list_skills():
            assert "name" in s
            assert "label" in s
            assert "description" in s
            assert "fields" in s


class TestRunScreener:
    @pytest.mark.asyncio
    async def test_run_no_source(self):
        with patch("app.screener.engine.get_source_for_market", return_value=None):
            result = await run_screener({})
            assert result["results"] == []
            assert "warning" in result

    @pytest.mark.asyncio
    async def test_run_pass1_only(self):
        mock_source = MagicMock()
        mock_source.name = "tonghuashun"
        mock_source.fetch_market_snapshot = AsyncMock(return_value=[
            {"code": "sh.600519", "name": "贵州茅台", "change_pct": 5.5, "amount": 10000000, "amplitude": 3.2},
            {"code": "sz.000001", "name": "平安银行", "change_pct": -1.0, "amount": 5000000, "amplitude": 2.0},
        ])
        mock_source.fetch_ticker_list = AsyncMock(return_value=[])

        with patch("app.screener.engine.get_source_for_market", return_value=mock_source):
            # Clear cache
            import app.screener.engine as eng
            eng._SNAP_CACHE["snap"] = None
            result = await run_screener({"change_pct": {"min": 3}})
            assert result["count"] == 1
            assert result["results"][0]["code"] == "sh.600519"
            assert "factor_details" in result["results"][0]

    @pytest.mark.asyncio
    async def test_run_pass2_limit_50(self):
        mock_stocks = [
            {"code": f"sh.60000{i}", "name": f"股票{i}", "change_pct": 5.0, "amount": 10000000}
            for i in range(60)
        ]
        mock_source = MagicMock()
        mock_source.name = "tonghuashun"
        mock_source.fetch_market_snapshot = AsyncMock(return_value=mock_stocks)
        mock_source.fetch_ticker_list = AsyncMock(return_value=[])

        with patch("app.screener.engine.get_source_for_market", return_value=mock_source):
            import app.screener.engine as eng
            eng._SNAP_CACHE["snap"] = None
            with patch("app.screener.engine._apply_pass2", AsyncMock(return_value=mock_stocks[:50])):
                result = await run_screener({"roe": {"min": 10}})
                assert result["count"] <= 50

    @pytest.mark.asyncio
    async def test_factor_details_snapshot(self):
        """Pass1 results should have factor_details for snapshot fields."""
        mock_source = MagicMock()
        mock_source.name = "tonghuashun"
        mock_source.fetch_market_snapshot = AsyncMock(return_value=[
            {"code": "sh.600519", "name": "茅台", "change_pct": 5.5, "amount": 10000000, "amplitude": 3.2},
        ])
        mock_source.fetch_ticker_list = AsyncMock(return_value=[])

        with patch("app.screener.engine.get_source_for_market", return_value=mock_source):
            import app.screener.engine as eng
            eng._SNAP_CACHE["snap"] = None
            result = await run_screener({"change_pct": {"min": 3}, "amount": {"min": 5000000}})
            stock = result["results"][0]
            assert "factor_details" in stock
            assert "change_pct" in stock["factor_details"]
            assert stock["factor_details"]["change_pct"]["pass"] == True
            assert stock["factor_details"]["change_pct"]["actual"] == 5.5


# === AI natural-language scan (Task 1) ===

class TestAIScan:
    def test_ai_scan_returns_sse_stream(self, client):
        """AI scan should return SSE text/event-stream."""
        with patch("app.api.v1.screener._read_subprocess") as mock_sub:
            # Simulate hermes output
            def fake_read(prompt, queue, ready_event):
                ready_event.set()
                queue.put_nowait("## 选股分析\n")
                queue.put_nowait("根据您的意图，我筛选出以下股票：\n")
                queue.put_nowait(None)
                queue.put_nowait(0)
                queue.put_nowait("")
            mock_sub.side_effect = fake_read

            resp = client.post("/api/v1/screener/ai-scan", json={
                "message": "找超跌反弹股",
                "skill": "",
                "use_skill": False,
            })
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        # Should contain SSE events
        assert "data:" in resp.text
        assert '"type"' in resp.text

    def test_ai_scan_with_skill(self, client):
        """AI scan with skill should include skill content in prompt."""
        with patch("app.api.v1.screener._read_subprocess") as mock_sub:
            captured_prompt = []
            def fake_read(prompt, queue, ready_event):
                ready_event.set()
                captured_prompt.append(prompt)
                queue.put_nowait("分析完成\n")
                queue.put_nowait(None)
                queue.put_nowait(0)
                queue.put_nowait("")
            mock_sub.side_effect = fake_read

            with patch("app.api.v1.screener._resolve_skill_content", return_value="## 超跌反弹策略\nRSI<30"):
                resp = client.post("/api/v1/screener/ai-scan", json={
                    "message": "找超跌股",
                    "skill": "oversold-bounce",
                    "use_skill": True,
                })
        assert resp.status_code == 200
        assert "RSI<30" in captured_prompt[0]

    def test_ai_scan_without_skill(self, client):
        """AI scan with use_skill=False should NOT include skill content."""
        with patch("app.api.v1.screener._read_subprocess") as mock_sub:
            captured_prompt = []
            def fake_read(prompt, queue, ready_event):
                ready_event.set()
                captured_prompt.append(prompt)
                queue.put_nowait("分析完成\n")
                queue.put_nowait(None)
                queue.put_nowait(0)
                queue.put_nowait("")
            mock_sub.side_effect = fake_read

            resp = client.post("/api/v1/screener/ai-scan", json={
                "message": "找超跌股",
                "skill": "oversold-bounce",
                "use_skill": False,
            })
        assert resp.status_code == 200
        assert "超跌反弹策略" not in captured_prompt[0]
