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

    # Build stock data context
    stock_data = ""
    for s in stocks:
        code = s["code"]
        try:
            data, _ = await data_engine.get_realtime(code)
            financial, _ = await data_engine.get_financial(code)
            bars, _ = await data_engine.get_klines(code, "daily", "2026-06-01", "2026-07-03")
            from app.indicators import compute_all
            indicators = await compute_all(bars[-60:]) if bars else []
            last_ind = indicators[-1] if indicators else {}

            price = data.get("price", "N/A") if data else "N/A"
            pct = data.get("change_pct", 0) if data else 0
            stock_data += f"\n## {s['name']} ({code})\n"
            stock_data += f"- 最新价: ¥{price} ({pct:+.2f}%)\n"
            if financial:
                stock_data += f"- ROE: {financial.get('roe', 'N/A')}% | 负债率: {financial.get('debt_ratio', 'N/A')}%\n"
            if last_ind and last_ind.get("macd"):
                m = last_ind["macd"]
                stock_data += f"- MACD: dif={m['dif']:.2f} dea={m['dea']:.2f} macd={m['macd']:.2f}\n"
            if last_ind and last_ind.get("rsi"):
                stock_data += f"- RSI(14): {last_ind['rsi']['rsi14']}\n"
            if last_ind and last_ind.get("kdj") and last_ind["kdj"]["k"]:
                kdj = last_ind["kdj"]
                stock_data += f"- KDJ: k={kdj['k']:.1f} d={kdj['d']:.1f} j={kdj['j']:.1f}\n"
            if last_ind and last_ind.get("boll") and last_ind["boll"]["mid"]:
                b = last_ind["boll"]
                stock_data += f"- 布林带: upper={b['upper']:.1f} mid={b['mid']:.1f} lower={b['lower']:.1f}\n"
        except Exception:
            pass

    prompt = f"""以下是当前股票数据，请进行分析回答用户问题。

{stock_data}

用户问题: {req.message}

请基于以上真实数据进行分析。如果数据不足以回答，说明需要哪些额外数据。"""

    async def event_stream():
        yield f'data: {{"session_id": "{sid}"}}\n\n'

        try:
            env = {**os.environ, "NO_COLOR": "1"}
            proc = subprocess.Popen(
                ["hermes", "chat", "-q", prompt, "-s", "stock-analysis"],
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
