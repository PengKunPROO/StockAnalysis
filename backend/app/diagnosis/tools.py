"""Tool definitions and handlers for AI diagnosis."""
import json
from app.engine.data_engine import engine
from app.indicators import compute_all

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_kline",
            "description": "获取股票K线数据，返回OHLCV数组。用于分析趋势、形态、支撑阻力位。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "股票代码，如 sh.600519"},
                    "period": {"type": "string", "enum": ["daily", "weekly", "monthly"]},
                    "limit": {"type": "integer", "description": "最近多少条数据，默认60"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_indicators",
            "description": "获取技术指标：MACD、RSI(14)、KDJ、BOLL(20)。用于分析买卖信号、超买超卖。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "股票代码"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_financials",
            "description": "获取财务数据：营收、净利润、ROE、PE、PB、资产负债率。用于基本面分析。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "股票代码"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_realtime",
            "description": "获取最新行情：当前价格、涨跌幅。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "股票代码"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_stocks",
            "description": "搜索股票。当用户提及的股票不在已知列表时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "股票名称或代码"}
                },
                "required": ["keyword"]
            }
        }
    },
]


async def execute_tool(name: str, args: dict) -> str:
    """Execute a tool and return JSON string result."""
    from datetime import date, timedelta

    if name == "get_kline":
        code = args["code"]
        period = args.get("period", "daily")
        limit = args.get("limit", 60)
        end = str(date.today())
        start = str(date.today() - timedelta(days=limit * 3))
        data, _ = await engine.get_klines(code, period, start, end)
        return json.dumps(data[-limit:], ensure_ascii=False)

    elif name == "get_indicators":
        code = args["code"]
        end = str(date.today())
        start = str(date.today() - timedelta(days=180))
        klines, _ = await engine.get_klines(code, "daily", start, end)
        if not klines:
            return json.dumps({"error": "No data"}, ensure_ascii=False)
        indicators = await compute_all(klines[-60:])
        return json.dumps(indicators[-10:], ensure_ascii=False)

    elif name == "get_financials":
        code = args["code"]
        data, _ = await engine.get_financial(code)
        return json.dumps(data, ensure_ascii=False)

    elif name == "get_realtime":
        code = args["code"]
        data, _ = await engine.get_realtime(code)
        return json.dumps(data, ensure_ascii=False)

    elif name == "search_stocks":
        keyword = args["keyword"]
        results, _ = await engine.search(keyword)
        return json.dumps(results[:5], ensure_ascii=False)

    return json.dumps({"error": f"Unknown tool: {name}"})
