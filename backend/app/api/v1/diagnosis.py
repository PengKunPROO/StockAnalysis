from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.diagnosis.engine import run_chat
from app.diagnosis.sessions import (
    create_session, add_stock_to_session, get_session_stocks,
    get_messages, list_sessions,
)

router = APIRouter(prefix="/diagnosis", tags=["diagnosis"])


class ChatRequest(BaseModel):
    session_id: str | None = None
    skill: str = "默认分析"
    model: str = "deepseek-v4-pro"
    message: str
    stock_codes: list[dict] | None = None


@router.post("/chat")
async def chat(req: ChatRequest):
    sid = req.session_id
    if not sid:
        sid = await create_session(req.skill, req.model, req.stock_codes or [])
    elif req.stock_codes:
        for s in req.stock_codes:
            await add_stock_to_session(sid, s["code"], s["name"])

    async def event_stream():
        yield f"data: {{\"session_id\": \"{sid}\"}}\n\n"
        async for chunk in run_chat(sid, req.message):
            yield chunk

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/sessions")
async def api_list_sessions():
    return {"sessions": await list_sessions()}


@router.get("/sessions/{session_id}")
async def api_get_session(session_id: str):
    stocks = await get_session_stocks(session_id)
    messages = await get_messages(session_id)
    return {"session_id": session_id, "stocks": stocks, "messages": messages}
