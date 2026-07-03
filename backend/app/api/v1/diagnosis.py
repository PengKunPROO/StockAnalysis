from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio, json, os, uuid, subprocess, re
from concurrent.futures import ThreadPoolExecutor

# Filter Hermes output: strip ANSI, remove boilerplate
ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')
def _filter_line(line: str) -> str | None:
    """Clean Hermes output: strip ANSI, skip boilerplate. Returns filtered line or None to skip."""
    clean = ANSI_RE.sub('', line)
    for pat in SKIP_PATTERNS:
        if re.match(pat, clean):
            return None
    return clean


SKIP_PATTERNS = [
    r'^Query:',
    r'^Initializing agent',
    r'^[─╭╰═╮╯]+',
    r'^Resume this session',
    r'^Session:',
    r'^Duration:',
    r'^Messages:',
    r'^name:',
    r'^description:',
    r'^mode:',
    r'^---',
]
from app.diagnosis.sessions import (
    create_session, add_stock_to_session, get_session_stocks,
    get_messages, list_sessions, save_message,
)
from app.diagnosis.skills_manager import get_skill_content
from app.engine.data_engine import engine as data_engine

router = APIRouter(prefix="/diagnosis", tags=["diagnosis"])


class ChatRequest(BaseModel):
    session_id: str | None = None
    skill: str = "stock-analysis"
    message: str
    stock_codes: list[dict] | None = None


@router.post("/chat")
async def chat(req: ChatRequest):
    sid = req.session_id
    if not sid:
        sid = await create_session(req.skill, "hermes", req.stock_codes or [])
    elif req.stock_codes:
        for s in req.stock_codes:
            await add_stock_to_session(sid, s["code"], s["name"])

    stocks = await get_session_stocks(sid)

    # Agent mode: give Hermes curl instructions instead of pre-fetching all data
    stock_list = ", ".join(f"{s['name']}({s['code']})" for s in stocks)
    skill_content = get_skill_content(req.skill) or ""

    prompt = f"""{skill_content}

你是股票分析 Agent。可以通过终端运行 curl 获取数据。后端运行在 localhost:8002。

## 可用数据 API:
- 搜索: curl -s "http://localhost:8002/api/v1/search?q=<关键词>"
- K线: curl -s "http://localhost:8002/api/v1/stock/<代码>/kline?period=daily&start=YYYY-MM-DD&end=YYYY-MM-DD"
- 实时: curl -s "http://localhost:8002/api/v1/stock/<代码>/realtime"
- 财务: curl -s "http://localhost:8002/api/v1/stock/<代码>/financial"
- 指标: curl -s "http://localhost:8002/api/v1/stock/<代码>/indicators?days=60"

## 当前标的: {stock_list}

## 规则:
1. 需要数据时主动 curl 获取，不要编造
2. 股票代码格式: sh.600519, sz.000001
3. 数据返回 JSON，提取相关字段分析
4. 用 Markdown 表格呈现关键指标
5. 给出客观分析，不做买卖建议

用户问题: {req.message}
"""

    async def event_stream():
        yield f'data: {{"session_id": "{sid}"}}\n\n'

        try:
            env = {**os.environ, "NO_COLOR": "1"}
            proc = subprocess.Popen(
                ["hermes", "chat", "-q", prompt],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=env, text=True, encoding="utf-8", errors="replace",
            )

            full_output = ""
            for line in proc.stdout:
                filtered = _filter_line(line)
                if filtered is not None:
                    full_output += filtered
                    yield f"data: {json.dumps({'content': filtered}, ensure_ascii=False)}\n\n"

            proc.wait()

            if proc.returncode != 0:
                stderr_text = proc.stderr.read().strip()
                err = stderr_text or f"Hermes exited with code {proc.returncode}"
                yield f"data: {json.dumps({'content': f'Agent Error: {err}', 'done': True}, ensure_ascii=False)}\n\n"
                return

            await save_message(sid, "user", content=req.message)
            await save_message(sid, "assistant", content=full_output.strip())
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            msg = f"Error: {e}\n{tb[-300:]}"
            yield f"data: {json.dumps({'content': msg, 'done': True}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/sessions")
async def api_list_sessions():
    return {"sessions": await list_sessions()}


@router.get("/sessions/{session_id}")
async def api_get_session(session_id: str):
    stocks = await get_session_stocks(session_id)
    messages = await get_messages(session_id)
    return {"session_id": session_id, "stocks": stocks, "messages": messages}
