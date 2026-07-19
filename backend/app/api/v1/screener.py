"""选股器 (screener) API: declarative fields, skill presets, two-pass run."""
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio, json, os, subprocess
from concurrent.futures import ThreadPoolExecutor
from app.screener import get_fields, run_screener, list_skills
from app.screener.fields import SORTABLE
from app.api.v1.diagnosis import (
    _resolve_skill_content, _classify_line,
    _resolve_hermes_binary, _read_subprocess, _shell_quote,
)

router = APIRouter(prefix="/screener", tags=["screener"])

@router.get("/fields")
async def fields():
    fl = get_fields()
    categories: list[str] = []
    for f in fl:
        if f.category not in categories:
            categories.append(f.category)
    return {"fields": [f.model_dump() for f in fl], "categories": categories}


@router.get("/skills")
async def skills():
    return {"skills": list_skills()}


class RunRequest(BaseModel):
    fields: dict  # {field_name: {"min":x,"max":y} | True}
    sort: str = "change_pct"
    limit: int = 50


@router.post("/run")
async def run(req: RunRequest):
    sort = req.sort if req.sort in SORTABLE else "change_pct"
    limit = max(1, min(req.limit, 200))
    result = await run_screener(req.fields, sort=sort, limit=limit)
    return result


# === AI 自然语言选股 ===

class AIScanRequest(BaseModel):
    message: str
    skill: str = ""
    use_skill: bool = True
    stock_codes: list[dict] = []


@router.post("/ai-scan")
async def ai_scan(req: AIScanRequest):
    skill_content = ""
    if req.use_skill and req.skill:
        skill_content = _resolve_skill_content(req.skill)

    stock_list = (
        ", ".join(f"{s.get('name','')}({s.get('code','')})" for s in req.stock_codes)
        if req.stock_codes
        else "全市场"
    )

    # NOTE: Prompt is a plain string (no f-string) so JSON braces in curl examples
    # are preserved literally. Slots are filled via .format() below.
    prompt_template = """{skill_content}

你是 A 股选股 Agent。可以通过终端运行 curl 获取数据。后端运行在 localhost:8002。

## 可用数据 API (每次 curl 加 --max-time 15):
- 全市场快照: curl -s --max-time 15 "http://localhost:8002/api/v1/intelligence/overview"
- 选股器: curl -s --max-time 15 -X POST "http://localhost:8002/api/v1/screener/run" -H "Content-Type: application/json" -d '{{"fields":{{"rsi_oversold":true}},"limit":20}}'
- K线: curl -s --max-time 15 "http://localhost:8002/api/v1/stock/<代码>/kline?period=daily&start=YYYY-MM-DD&end=YYYY-MM-DD"
- 实时: curl -s --max-time 15 "http://localhost:8002/api/v1/stock/<代码>/realtime"
- 财务: curl -s --max-time 15 "http://localhost:8002/api/v1/stock/<代码>/financial"
- 指标: curl -s --max-time 15 "http://localhost:8002/api/v1/stock/<代码>/indicators?days=60"
- 涨停池: curl -s --max-time 15 "http://localhost:8002/api/v1/intelligence/limit-up"
- 龙虎榜: curl -s --max-time 15 "http://localhost:8002/api/v1/intelligence/dragon-tiger"
- 热榜: curl -s --max-time 15 "http://localhost:8002/api/v1/intelligence/fund-flow"

## 选股器 fields 参数说明 (JSON):
可用因子:
- change_pct: 涨跌幅(%)
- amount: 成交额(元), 1亿=100000000
- amplitude: 振幅(%)
- rsi_oversold: RSI超卖(boolean true)
- macd_golden_cross: MACD金叉(boolean true)
- boll_breakout: 布林突破(boolean true)
- roe: ROE(%)
- debt_ratio: 负债率(%)
- near_high_drop: 距52周高点跌幅(%)
- change_5d: 5日涨跌幅(%)
- change_20d: 20日涨跌幅(%)
- on_dragon_tiger: 龙虎榜上榜(boolean true)

示例:
curl -s --max-time 15 -X POST "http://localhost:8002/api/v1/screener/run" \\
  -H "Content-Type: application/json" \\
  -d '{{"fields":{{"rsi_oversold":true,"near_high_drop":{{"min":30}},"amount":{{"min":100000000}}}},"limit":20}}'

## 规则:
1. 分析用户意图，确定需要哪些筛选因子
2. 如果有 skill，优先参考 skill 中的选股逻辑和阈值建议
3. 先用选股器 API 粗筛，再对结果逐个 curl 获取详细数据
4. 每只候选股票给出入选理由（技术面/基本面/消息面）
5. 返回 5-15 只候选股票，按推荐度排序
6. 不编造数据，curl 失败明确说明
7. 排除 ST 股、退市风险股

## 输出格式:
先用 Markdown 列出分析过程，最后输出候选股票表格:
| 代码 | 名称 | 现价 | 涨跌幅 | 入选理由 |
|------|------|------|--------|----------|
然后给出整体分析和操作建议。

## 当前标的范围: {stock_list}

用户意图: {req_message}
"""

    prompt = prompt_template.format(
        skill_content=skill_content,
        stock_list=stock_list,
        req_message=req.message,
    )

    async def event_stream():
        yield f'data: {json.dumps({"type":"status","status":"agent_starting"}, ensure_ascii=False)}\n\n'

        queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=1)
        ready_event = asyncio.Event()
        loop.run_in_executor(executor, _read_subprocess, prompt, queue, ready_event)

        full_output = ""
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                continue

            if item is None:
                break
            if isinstance(item, Exception):
                yield f'data: {json.dumps({"type":"error","content": f"Error: {item}"}, ensure_ascii=False)}\n\n'
                yield f'data: {json.dumps({"type":"done"}, ensure_ascii=False)}\n\n'
                executor.shutdown(wait=False)
                return

            line = item if isinstance(item, str) else str(item)
            event_type, content = _classify_line(line)

            if event_type == "skip":
                continue
            elif event_type == "log":
                if content and "curl" in content:
                    yield f'data: {json.dumps({"type":"status","status":"fetching_data"}, ensure_ascii=False)}\n\n'
                yield f'data: {json.dumps({"type":"log","content": content}, ensure_ascii=False)}\n\n'
            elif event_type == "analysis":
                full_output += content + "\n"
                analysis_chunk = content + "\n"
                yield f'data: {json.dumps({"type":"analysis","content": analysis_chunk}, ensure_ascii=False)}\n\n'

        try:
            returncode = await asyncio.wait_for(queue.get(), timeout=5.0)
            stderr_text = await asyncio.wait_for(queue.get(), timeout=5.0)
        except (asyncio.TimeoutError, Exception):
            returncode = -1
            stderr_text = ""

        executor.shutdown(wait=True)

        if returncode != 0:
            err = stderr_text or f"Hermes exited with code {returncode}"
            yield f'data: {json.dumps({"type":"error","content": f"Agent Error: {err}"}, ensure_ascii=False)}\n\n'

        yield f'data: {json.dumps({"type":"done"}, ensure_ascii=False)}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
