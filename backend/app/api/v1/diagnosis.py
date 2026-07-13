from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio, json, os, uuid, subprocess, re
from concurrent.futures import ThreadPoolExecutor
from app.diagnosis.sessions import (
    create_session, add_stock_to_session, set_session_stocks,
    get_session_stocks, get_messages, list_sessions, save_message,
)
from app.diagnosis.skills_manager import get_skill_content
from app.diagnosis.hermes_skills import get_hermes_skill_content


def _resolve_skill_content(skill_name: str) -> str:
    """Resolve skill content from uploaded skills first, then hermes skills."""
    content = get_skill_content(skill_name)
    if content:
        return content
    content = get_hermes_skill_content(skill_name)
    if content:
        return content
    return ""

ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')
ANALYSIS_START = re.compile(r'╭─.*Hermes.*─+╮')
ANALYSIS_END = re.compile(r'╰─+')

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
    r'^hermes --resume',
    r'^\s*┊\s',
    r'^\s*$',
]


def _filter_line(line: str) -> str | None:
    clean = ANSI_RE.sub('', line).rstrip('\n')
    for pat in SKIP_PATTERNS:
        if re.match(pat, clean):
            return None
    return clean


def _read_subprocess(prompt: str, output_queue):
    try:
        env = {**os.environ, "NO_COLOR": "1"}
        proc = subprocess.Popen(
            ["hermes", "chat", "-q", prompt],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, text=True, encoding="utf-8", errors="replace",
        )
        for line in proc.stdout:
            output_queue.put_nowait(line)
        proc.wait()
        # Signal end: None followed by returncode and stderr
        stderr_text = proc.stderr.read().strip()
        output_queue.put_nowait(None)
        output_queue.put_nowait(proc.returncode)
        output_queue.put_nowait(stderr_text)
    except Exception as e:
        output_queue.put_nowait(e)

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
        await set_session_stocks(sid, req.stock_codes)

    stocks = await get_session_stocks(sid)

    stock_list = ", ".join(f"{s['name']}({s['code']})" for s in stocks)
    skill_content = _resolve_skill_content(req.skill)

    # Pre-fetch recent news context for analysis
    news_context = ""
    try:
        from app.engine.data_engine import engine
        for s in stocks[:3]:
            news_data, _ = await engine.get_news(s["code"], limit=5)
            if news_data:
                items = [f"  - {n['title']} ({n.get('published_at', '')[:10]})" for n in news_data[:3]]
                news_context += f"\n{s['name']}({s['code']}) 近期新闻:\n" + "\n".join(items)
    except Exception:
        pass

    prompt = f"""{skill_content}

你是股票分析 Agent。可以通过终端运行 curl 获取数据。后端运行在 localhost:8002。
当前使用的 Skill: {req.skill}

## 可用数据 API (每次 curl 加 --max-time 15):
- 搜索: curl -s --max-time 15 "http://localhost:8002/api/v1/search?q=<关键词>"
- K线: curl -s --max-time 15 "http://localhost:8002/api/v1/stock/<代码>/kline?period=daily&start=YYYY-MM-DD&end=YYYY-MM-DD"
- 实时: curl -s --max-time 15 "http://localhost:8002/api/v1/stock/<代码>/realtime"
- 财务: curl -s --max-time 15 "http://localhost:8002/api/v1/stock/<代码>/financial"
- 指标: curl -s --max-time 15 "http://localhost:8002/api/v1/stock/<代码>/indicators?days=60"
- 新闻: curl -s --max-time 15 "http://localhost:8002/api/v1/news/stock/<代码>"

## 当前标的: {stock_list}
{news_context}

## 规则:
1. 需要数据时主动 curl 获取，不要编造
2. 股票代码格式: sh.600519, sz.000001
3. 数据返回 JSON，提取相关字段分析
4. 用 Markdown 表格呈现关键指标
5. 给出客观分析，不做买卖建议
6. 如果 curl 返回空数据或错误，明确说明"数据获取失败"，绝不编造价格或指标

用户问题: {req.message}
"""

    async def event_stream():
        yield f'data: {{"session_id": "{sid}"}}\n\n'
        yield f'data: {json.dumps({"status": "agent_starting"}, ensure_ascii=False)}\n\n'

        queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=1)
        loop.run_in_executor(executor, _read_subprocess, prompt, queue)

        full_output = ""
        in_analysis = False
        line_count = 0
        returncode = 0
        stderr_text = ""

        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, Exception):
                yield f"data: {json.dumps({'content': f'Error: {item}', 'done': True}, ensure_ascii=False)}\n\n"
                executor.shutdown(wait=False)
                return

            line = item if isinstance(item, str) else str(item)
            line_count += 1

            if not in_analysis:
                clean = ANSI_RE.sub('', line)
                if ANALYSIS_START.search(clean):
                    in_analysis = True
                    continue
                # Fallback: if no analysis marker found after 30 lines,
                # start treating all non-skip lines as content
                if line_count > 30:
                    in_analysis = True
                    # Fall through to process this line as content
                else:
                    continue

            clean = ANSI_RE.sub('', line)
            if ANALYSIS_END.search(clean):
                continue

            filtered = _filter_line(line)
            if filtered is not None:
                full_output += filtered + "\n"
                if "$" in filtered and "curl" in filtered:
                    yield f'data: {json.dumps({{"status": "fetching_data"}}, ensure_ascii=False)}\n\n'
                chunk = filtered + "\n"
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"

        # Read final signals
        try:
            returncode = await queue.get()
            stderr_text = await queue.get()
        except Exception:
            returncode = -1
            stderr_text = ""

        executor.shutdown(wait=True)

        if returncode != 0:
            err = stderr_text or f"Hermes exited with code {returncode}"
            yield f"data: {json.dumps({'content': f'Agent Error: {err}', 'done': True}, ensure_ascii=False)}\n\n"
            return

        await save_message(sid, "user", content=req.message)
        await save_message(sid, "assistant", content=full_output.strip())
        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/sessions")
async def api_list_sessions():
    return {"sessions": await list_sessions()}


@router.get("/sessions/{session_id}")
async def api_get_session(session_id: str):
    stocks = await get_session_stocks(session_id)
    messages = await get_messages(session_id)
    return {"session_id": session_id, "stocks": stocks, "messages": messages}
