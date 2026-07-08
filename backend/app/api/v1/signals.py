"""操作建议 (signals) API: rule engine + DeepSeek SSE AI interpretation."""
import json
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.config import settings
from app.engine.data_engine import engine
from app.indicators import compute_all, compute_fibonacci_levels
from app.signals import compute_signals

router = APIRouter(prefix="/signals", tags=["signals"])


async def _load_context(code: str, days: int = 90):
    """Fetch klines + indicators + fibonacci for a stock."""
    from datetime import date, timedelta
    end = str(date.today())
    start = str(date.today() - timedelta(days=days * 2))
    klines, warn = await engine.get_klines(code, "daily", start, end)
    if not klines:
        return None, None, None, warn
    window = klines[-days:]
    indicators = await compute_all(window)
    fibonacci = await compute_fibonacci_levels(klines)
    return window, indicators, fibonacci, warn


@router.get("/{code}")
async def get_signals(code: str, days: int = 90):
    klines, indicators, fibonacci, warn = await _load_context(code, days)
    if klines is None:
        raise HTTPException(status_code=503, detail={"error": warn or "数据源暂不可用"})
    payload = compute_signals(klines, indicators, fibonacci)
    if warn:
        payload["warning"] = warn
    payload["code"] = code
    return payload


@router.post("/{code}/ai")
async def ai_interpret(code: str, days: int = 90):
    """SSE stream: rule signals first, then DeepSeek interpretation."""
    klines, indicators, fibonacci, warn = await _load_context(code, days)
    if klines is None:
        raise HTTPException(status_code=503, detail={"error": warn or "数据源暂不可用"})
    payload = compute_signals(klines, indicators, fibonacci)

    recent = indicators[-10:] if indicators else []
    close = klines[-1]["close"]
    context = {
        "code": code,
        "close": close,
        "signals": payload["active_signals"],
        "score": payload["score"],
        "key_levels": payload["key_levels"],
        "risk": payload["risk"],
        "rule_summary": payload["summary"],
        "recent_indicators": [
            {
                "date": b.get("date"),
                "macd": b.get("macd"),
                "rsi": b.get("rsi"),
                "kdj": b.get("kdj"),
                "boll": b.get("boll"),
            }
            for b in recent
        ],
    }

    api_key = settings.diagnosis_llm_api_key
    base_url = settings.diagnosis_llm_base_url
    model = settings.diagnosis_llm_model or "deepseek-chat"

    system_prompt = (
        "你是A股市场分析顾问。基于后端实时计算的规则信号数据（MACD/RSI/KDJ/BOLL/ATR/斐波那契），"
        "给出客观的市场环境解读、信号解读与含具体价格区间的操作建议。\n"
        "规则：1) 禁止使用Markdown格式，用纯文本分段；2) 引用具体数值；"
        "3) 给出明确的买入区间、止损价、目标价、仓位；4) 结尾必须附风险提示。"
    )
    user_prompt = (
        f"股票代码: {code}\n当前价: {close}\n\n"
        f"规则信号数据(JSON):\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
        "请基于以上数据给出操作建议解读。"
    )

    async def event_stream():
        # 1) emit rule signals immediately so UI can render骨架
        yield f"data: {json.dumps({'type': 'signals', 'data': payload}, ensure_ascii=False)}\n\n"

        if not api_key:
            yield f"data: {json.dumps({'type': 'error', 'content': 'AI 未配置（缺少 LLM API key），请查看规则信号 Tab。'}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            return

        # 2) stream DeepSeek completion
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.4,
                        "max_tokens": 1200,
                        "stream": True,
                    },
                ) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        body_text = body.decode(errors="replace")[:200]
                        yield f"data: {json.dumps({'type': 'error', 'content': f'LLM 返回 {resp.status_code}: {body_text}'}, ensure_ascii=False)}\n\n"
                        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                        return
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        chunk = line[5:].strip()
                        if chunk == "[DONE]":
                            break
                        try:
                            obj = json.loads(chunk)
                            delta = obj.get("choices", [{}])[0].get("delta", {})
                            # deepseek-v4-pro 等推理模型: 答案在 reasoning_content, content 为空。
                            # 同时捕获两者, 前端区分显示(兼容非推理模型)。
                            reasoning = delta.get("reasoning_content")
                            content = delta.get("content")
                            if reasoning:
                                yield f"data: {json.dumps({'type': 'reasoning', 'content': reasoning}, ensure_ascii=False)}\n\n"
                            if content:
                                yield f"data: {json.dumps({'type': 'content', 'content': content}, ensure_ascii=False)}\n\n"
                        except (json.JSONDecodeError, IndexError):
                            continue
        except httpx.HTTPError as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'AI 请求失败: {e}'}, ensure_ascii=False)}\n\n"

        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
