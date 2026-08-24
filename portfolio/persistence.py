import json
from dataclasses import asdict

from portfolio.portfolio_state import PortfolioState, Position, TradeRecord


def save_portfolio_state(state, path):
    payload = {
        "quote_balance": state.quote_balance,
        "starting_quote_balance": state.starting_quote_balance,
        "realized_pnl": state.realized_pnl,
        "total_fees_paid": state.total_fees_paid,
        "positions": {symbol: asdict(position) for symbol, position in state.positions.items()},
        "trade_log": [asdict(trade) for trade in state.trade_log],
    }

    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


def load_portfolio_state(path):
    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as file:
        payload = json.load(file)

    return PortfolioState(
        quote_balance=payload["quote_balance"],
        starting_quote_balance=payload["starting_quote_balance"],
        realized_pnl=payload["realized_pnl"],
        total_fees_paid=payload["total_fees_paid"],
        positions={symbol: Position(**data) for symbol, data in payload["positions"].items()},
        trade_log=[TradeRecord(**data) for data in payload["trade_log"]],
    )
