# backend/app/portfolio/analyzer.py
"""Three-stage analysis pipeline: rules -> DeepSeek per-stock -> DeepSeek summary."""
import json
import httpx
import logging
from datetime import date, timedelta
from typing import Any
from app.config import settings
from app.diagnosis.tools import execute_tool, TOOL_DEFINITIONS
from app.diagnosis.skills_manager import get_skill_content

logger = logging.getLogger(__name__)

DEFAULT_SKILL = "stock-analysis"


async def analyze_stock(
    code: str, name: str, holding_ctx: dict, prev_advice: dict | None,
) -> dict[str, Any]:
    """Stage 2: Analyze a single stock via DeepSeek function-calling.

    Returns dict with: advice, buy_range, stop_loss, target, analysis (str).
    On failure returns {"error": "...", "status": "failed"}.
    """
    skill_content = get_skill_content(DEFAULT_SKILL) or ""

    system_prompt = f"""{skill_content}

你是专业股票分析师。基于工具获取的数据，分析以下股票并给出操作建议。

当前持仓上下文：
- 股票: {name}({code})
- 持仓: {holding_ctx.get('shares', 0)} 股
- 成本价: {holding_ctx.get('avg_cost', 0)}
- 仓位占比: {holding_ctx.get('weight', 0):.1%}
- 浮动盈亏: {holding_ctx.get('pnl', 0):.2f} ({holding_ctx.get('pnl_pct', 0):.1f}%)

"""

    if prev_advice:
        system_prompt += f"前日建议: {prev_advice.get('advice_text', '无')} (建议类型: {prev_advice.get('advice_type', '无')})\n"
        system_prompt += "请对比前日建议和当前走势，判断建议是否仍然有效。\n"

    system_prompt += """
请调用工具获取K线、指标、财务、新闻、实时行情数据，然后给出分析。

最终回复必须是 JSON 格式：
{
  "advice": "buy|sell|hold|watch|stop_loss",
  "buy_range": "1750-1820",
  "stop_loss": 1680,
  "target": 1950,
  "analysis": "详细分析文本（Markdown）"
}
"""

    user_prompt = f"请分析 {name}({code}) 的当前走势并给出操作建议。"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    max_rounds = settings.diagnosis_max_tool_rounds
    model = settings.diagnosis_llm_model

    try:
        for round_num in range(max_rounds + 1):
            response = await _call_deepseek(messages, model)
            message = response.get("choices", [{}])[0].get("message", {})

            if message.get("tool_calls"):
                messages.append({"role": "assistant", "tool_calls": message["tool_calls"]})
                for tc in message["tool_calls"]:
                    func_name = tc["function"]["name"]
                    func_args = json.loads(tc["function"]["arguments"])
                    result = await execute_tool(func_name, func_args)
                    messages.append({
                        "role": "tool", "tool_call_id": tc["id"], "content": result
                    })
            else:
                content = message.get("content", "")
                # Try to parse JSON from content
                try:
                    # Find JSON in response
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start >= 0 and end > start:
                        parsed = json.loads(content[start:end])
                        parsed["status"] = "success"
                        return parsed
                except (json.JSONDecodeError, ValueError):
                    pass
                # Fallback: return raw content
                return {
                    "advice": "hold",
                    "analysis": content,
                    "status": "success",
                }

        return {"error": "Max rounds reached", "status": "failed"}

    except Exception as e:
        logger.error(f"Stock analysis failed for {code}: {e}")
        return {"error": str(e), "status": "failed"}


async def generate_summary(
    portfolio_analysis: dict, stock_analyses: list[dict],
    prev_contexts: list[dict],
) -> str:
    """Stage 3: Generate overall summary via DeepSeek."""
    skill_content = get_skill_content(DEFAULT_SKILL) or ""

    system_prompt = f"""{skill_content}

你是投资组合管理顾问。基于组合分析和逐股分析结果，生成今日整体操作指导。

请输出 Markdown 格式：
1. 整体操作指导摘要
2. 行动计划列表（每只股票的操作建议 + 优先级）
3. 风险提示
"""

    context = {
        "portfolio": portfolio_analysis,
        "stock_analyses": [
            {"code": s.get("code"), "advice": s.get("advice"), "analysis": s.get("analysis", "")[:200]}
            for s in stock_analyses
        ],
        "previous_advice": [
            {"stock": c.get("stock_code"), "advice": c.get("advice_text"), "executed": c.get("executed")}
            for c in prev_contexts
        ],
    }

    user_prompt = f"组合分析数据(JSON):\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\n请生成今日操作指导。"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = await _call_deepseek(messages, settings.diagnosis_llm_model)
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        return f"操作指导生成失败: {e}"


async def _call_deepseek(messages: list[dict], model: str) -> dict:
    """Call DeepSeek API directly (no diagnosis session)."""
    key = settings.diagnosis_llm_api_key
    base_url = settings.diagnosis_llm_base_url

    async with httpx.AsyncClient(timeout=120) as client:
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
                "max_tokens": 4096,
            },
        )
        resp.raise_for_status()
        return resp.json()
