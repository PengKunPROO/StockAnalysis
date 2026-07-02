"""AI Diagnosis Engine — Function Calling + SSE streaming."""
import json
import httpx
import logging
from typing import AsyncGenerator
from app.config import settings
from app.diagnosis.tools import TOOL_DEFINITIONS, execute_tool
from app.diagnosis.skills_manager import get_skill_content
from app.diagnosis.sessions import get_session_stocks, get_messages, save_message

logger = logging.getLogger(__name__)


async def run_chat(session_id: str, user_message: str, api_key: str = "",
                   model_override: str = "") -> AsyncGenerator[str, None]:
    stocks = await get_session_stocks(session_id)
    messages = await get_messages(session_id)

    factory = __import__('app.db.database', fromlist=['get_session_factory']).get_session_factory()
    async with factory() as sess:
        from sqlalchemy import select
        from app.db.models import DiagnosisSession
        result = await sess.execute(
            select(DiagnosisSession).where(DiagnosisSession.id == session_id)
        )
        ds = result.scalar_one()

    skill_content = get_skill_content(ds.skill_name) or ""
    stock_list = ", ".join(f"{s['name']}({s['code']})" for s in stocks)

    system_prompt = f"""{skill_content}

当前可分析的股票: {stock_list}

你可以使用提供的工具函数查询股票数据。需要数据时请主动调用工具，不要猜测。
分析时引用具体数值，给出有理有据的判断。"""

    llm_messages = [{"role": "system", "content": system_prompt}]

    for m in messages[-20:]:
        msg = {"role": m["role"]}
        if m["content"]:
            msg["content"] = m["content"]
        if m["tool_calls"]:
            msg["tool_calls"] = json.loads(m["tool_calls"])
        if m["tool_call_id"]:
            msg["tool_call_id"] = m["tool_call_id"]
        llm_messages.append(msg)

    llm_messages.append({"role": "user", "content": user_message})
    await save_message(session_id, "user", content=user_message)

    max_rounds = settings.diagnosis_max_tool_rounds
    model = model_override or ds.model

    for round_num in range(max_rounds + 1):
        if round_num >= max_rounds:
            yield f"data: {json.dumps({'error': '达到最大工具调用轮次，请简化问题'}, ensure_ascii=False)}\n\n"
            return

        response = await _call_llm(llm_messages, model, api_key)
        message = response.get("choices", [{}])[0].get("message", {})

        if message.get("tool_calls"):
            tc_json = json.dumps(message["tool_calls"], ensure_ascii=False)
            await save_message(session_id, "assistant", tool_calls=tc_json)
            llm_messages.append({"role": "assistant", "tool_calls": message["tool_calls"]})

            for tc in message["tool_calls"]:
                func_name = tc["function"]["name"]
                func_args = json.loads(tc["function"]["arguments"])
                result = await execute_tool(func_name, func_args)
                await save_message(session_id, "tool", content=result, tool_call_id=tc["id"])
                llm_messages.append({
                    "role": "tool", "tool_call_id": tc["id"], "content": result
                })
        else:
            content = message.get("content", "")
            await save_message(session_id, "assistant", content=content)
            yield f"data: {json.dumps({'content': content, 'done': True}, ensure_ascii=False)}\n\n"
            return


async def _call_llm(messages: list[dict], model: str, api_key: str = "") -> dict:
    key = api_key or settings.diagnosis_llm_api_key
    base_url = settings.diagnosis_llm_base_url

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "tools": TOOL_DEFINITIONS,
                "temperature": 0.3,
                "max_tokens": 2000,
            },
        )
        resp.raise_for_status()
        return resp.json()
