"""Portfolio rule-based calculator - pure functions, no network."""
from datetime import datetime
from typing import Any


def calculate_portfolio_metrics(
    holdings: list[dict],
    transactions: list[dict],
    realtime_prices: dict[str, dict],
) -> dict[str, Any]:
    """Compute portfolio metrics from holdings + transactions + realtime prices.

    Pure function - no DB, no network. All data passed in as dicts.
    """
    if not holdings:
        return {
            "total_market_value": 0,
            "total_cost": 0,
            "total_pnl": 0,
            "pnl_pct": 0,
            "today_change": 0,
            "today_change_pct": 0,
            "holdings_count": 0,
            "position_weights": [],
            "industry_exposure": {},
            "concentration": {"hhi": 0, "max_weight": 0, "top3_weight": 0},
            "operation_stats": {
                "win_rate": 0,
                "total_closed_trades": 0,
                "avg_holding_days": 0,
                "avg_profit_loss_ratio": 0,
                "max_win_streak": 0,
                "max_loss_streak": 0,
                "recent_trades": [],
            },
        }

    # Per-holding market value
    enriched = []
    for h in holdings:
        rt = realtime_prices.get(h["code"], {})
        price = rt.get("price", h["avg_cost"])
        change_pct = rt.get("change_pct", 0)
        market_value = h["shares"] * price
        cost = h["shares"] * h["avg_cost"]
        pnl = market_value - cost
        pnl_pct = (pnl / cost * 100) if cost > 0 else 0
        today_change = market_value * change_pct / 100
        enriched.append({
            "code": h["code"], "name": h["name"],
            "shares": h["shares"], "avg_cost": h["avg_cost"],
            "industry": h.get("industry", "未分类"),
            "current_price": price,
            "market_value": market_value,
            "cost": cost, "pnl": pnl, "pnl_pct": pnl_pct,
            "change_pct": change_pct, "today_change": today_change,
        })

    total_mv = sum(e["market_value"] for e in enriched)
    total_cost = sum(e["cost"] for e in enriched)
    total_pnl = total_mv - total_cost
    pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
    today_change = sum(e["today_change"] for e in enriched)
    today_change_pct = (today_change / (total_mv - today_change) * 100) if (total_mv - today_change) > 0 else 0

    # Position weights (sorted desc)
    weights = sorted(
        [{"code": e["code"], "name": e["name"], "weight": e["market_value"] / total_mv if total_mv > 0 else 0,
          "market_value": e["market_value"]} for e in enriched],
        key=lambda x: x["weight"], reverse=True
    )

    # Industry exposure
    industry_map = {}
    for e in enriched:
        ind = e["industry"]
        industry_map[ind] = industry_map.get(ind, 0) + e["market_value"]
    industry_exposure = {k: v / total_mv for k, v in industry_map.items()} if total_mv > 0 else {}

    # Concentration
    max_weight = weights[0]["weight"] if weights else 0
    top3_weight = sum(w["weight"] for w in weights[:3])
    hhi = sum(w["weight"] ** 2 for w in weights) * 10000  # HHI index 0-10000

    # Operation stats from closed trades
    op_stats = _compute_operation_stats(transactions)

    return {
        "total_market_value": round(total_mv, 2),
        "total_cost": round(total_cost, 2),
        "total_pnl": round(total_pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "today_change": round(today_change, 2),
        "today_change_pct": round(today_change_pct, 2),
        "holdings_count": len(holdings),
        "position_weights": weights,
        "industry_exposure": industry_exposure,
        "concentration": {
            "hhi": round(hhi, 0),
            "max_weight": round(max_weight, 4),
            "top3_weight": round(top3_weight, 4),
        },
        "operation_stats": op_stats,
    }


def _compute_operation_stats(transactions: list[dict]) -> dict:
    """Match buy/sell pairs per stock to compute win rate, avg holding days, etc."""
    # Group by stock code
    by_code: dict[str, list[dict]] = {}
    for tx in transactions:
        code = tx["code"]
        by_code.setdefault(code, []).append(tx)

    closed_trades = []
    for code, txs in by_code.items():
        txs.sort(key=lambda t: t["traded_at"])
        buy_queue: list[dict] = []  # FIFO queue of buys
        for tx in txs:
            if tx["action"] == "buy":
                buy_queue.append(tx)
            elif tx["action"] == "sell" and buy_queue:
                # Match against oldest buy (FIFO)
                remaining = tx["shares"]
                while remaining > 0 and buy_queue:
                    buy = buy_queue[0]
                    matched = min(remaining, buy["shares"])
                    buy_date = datetime.fromisoformat(str(buy["traded_at"]).replace("Z", ""))
                    sell_date = datetime.fromisoformat(str(tx["traded_at"]).replace("Z", ""))
                    holding_days = (sell_date - buy_date).days
                    pnl = (tx["price"] - buy["price"]) * matched
                    closed_trades.append({
                        "code": code, "buy_price": buy["price"],
                        "sell_price": tx["price"], "shares": matched,
                        "holding_days": holding_days, "pnl": pnl,
                        "win": pnl > 0,
                        "sell_date": str(tx["traded_at"]),
                    })
                    remaining -= matched
                    buy["shares"] -= matched
                    if buy["shares"] <= 0:
                        buy_queue.pop(0)

    total_closed = len(closed_trades)
    wins = sum(1 for t in closed_trades if t["win"])
    win_rate = wins / total_closed if total_closed > 0 else 0

    avg_holding_days = (
        sum(t["holding_days"] for t in closed_trades) / total_closed
        if total_closed > 0 else 0
    )

    # Avg profit/loss ratio
    profits = [t["pnl"] for t in closed_trades if t["win"]]
    losses = [abs(t["pnl"]) for t in closed_trades if not t["win"]]
    avg_profit = sum(profits) / len(profits) if profits else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    avg_pl_ratio = avg_profit / avg_loss if avg_loss > 0 else 0

    # Win/loss streaks
    max_win_streak = 0
    max_loss_streak = 0
    current_win = 0
    current_loss = 0
    for t in closed_trades:
        if t["win"]:
            current_win += 1
            current_loss = 0
            max_win_streak = max(max_win_streak, current_win)
        else:
            current_loss += 1
            current_win = 0
            max_loss_streak = max(max_loss_streak, current_loss)

    # Recent trades (last 10)
    recent = sorted(closed_trades, key=lambda t: t.get("sell_date", ""), reverse=True)[:10]

    return {
        "win_rate": round(win_rate, 4),
        "total_closed_trades": total_closed,
        "avg_holding_days": round(avg_holding_days, 1),
        "avg_profit_loss_ratio": round(avg_pl_ratio, 2),
        "max_win_streak": max_win_streak,
        "max_loss_streak": max_loss_streak,
        "recent_trades": recent,
    }
