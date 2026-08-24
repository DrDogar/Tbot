import json
from dataclasses import asdict
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template

from bots.bot_configs import BOTS
from config.settings import (
    DECISION_ENGINE,
    STATE_DIR,
    TRACKED_SYMBOLS,
    WEB_MONITOR_HOST,
    WEB_MONITOR_PORT,
    WEB_MONITOR_REFRESH_SECONDS,
)
from engine.equity_history import load_equity_history
from engine.last_cycle import load_last_cycle
from engine.session_state import load_run_state, remaining_seconds
from exchange.binance import get_live_price
from portfolio.persistence import load_portfolio_state
from portfolio.valuation import compute_portfolio_summary

RUN_STATE_PATH = STATE_DIR / "run_state.json"
PORTFOLIO_STATE_PATH = STATE_DIR / "portfolio_state.json"
LAST_CYCLE_PATH = STATE_DIR / "last_cycle.json"
EQUITY_HISTORY_PATH = STATE_DIR / "equity_history.csv"
LOG_PATH = STATE_DIR / "session.log"

ARENA_DIR = STATE_DIR / "bots"
ARENA_RUN_STATE_PATH = ARENA_DIR / "run_state.json"
ARENA_TRAINING_PATH = ARENA_DIR / "training.json"
ARENA_LAST_CYCLE_PATH = ARENA_DIR / "last_cycle.json"
ARENA_LOG_PATH = STATE_DIR / "session.log"

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("monitor.html", refresh_seconds=WEB_MONITOR_REFRESH_SECONDS)


@app.route("/arena")
def arena():
    return render_template("arena.html", refresh_seconds=WEB_MONITOR_REFRESH_SECONDS)


@app.route("/api/status")
def api_status():
    run_state = load_run_state(RUN_STATE_PATH)
    portfolio = load_portfolio_state(PORTFOLIO_STATE_PATH)

    if run_state is None or portfolio is None:
        return jsonify({"session_active": False})

    last_cycle = load_last_cycle(LAST_CYCLE_PATH)
    now = datetime.now(timezone.utc)
    summary = compute_portfolio_summary(portfolio)

    coins = [_coin_payload(symbol, portfolio, last_cycle) for symbol in TRACKED_SYMBOLS]
    recent_trades = [asdict(trade) for trade in reversed(portfolio.trade_log[-25:])]
    equity_history = load_equity_history(EQUITY_HISTORY_PATH)
    recent_log = _tail_log(LOG_PATH, 60)

    return jsonify(
        {
            "session_active": True,
            "session": {
                "run_id": run_state.run_id,
                "started_at": run_state.started_at,
                "cycle_count": run_state.cycle_count,
                "completed": run_state.completed,
                "duration_hours": run_state.duration_hours,
                "interval_seconds": run_state.interval_seconds,
                "remaining_seconds": remaining_seconds(run_state, now),
                "decision_engine": DECISION_ENGINE,
            },
            "portfolio": {
                "starting_quote_balance": portfolio.starting_quote_balance,
                "cash": portfolio.quote_balance,
                "market_value": summary["market_value"],
                "equity": summary["equity"],
                "pnl": summary["pnl"],
                "pnl_pct": summary["pnl_pct"],
                "realized_pnl": portfolio.realized_pnl,
                "total_fees_paid": portfolio.total_fees_paid,
                "trade_count": len(portfolio.trade_log),
            },
            "coins": coins,
            "recent_trades": recent_trades,
            "equity_history": equity_history,
            "recent_log": recent_log,
        }
    )


@app.route("/api/arena-status")
def api_arena_status():
    run_state = load_run_state(ARENA_RUN_STATE_PATH)

    if run_state is None:
        return jsonify({"arena_active": False})

    now = datetime.now(timezone.utc)
    training = _load_json(ARENA_TRAINING_PATH) or {}
    last_cycle = _load_json(ARENA_LAST_CYCLE_PATH) or {}
    recent_log = _tail_log(ARENA_LOG_PATH, 80)
    live_prices = _fetch_live_prices(TRACKED_SYMBOLS)

    bots_payload = []

    for bot in BOTS:
        portfolio = load_portfolio_state(ARENA_DIR / f"portfolio_{bot.key}.json")

        if portfolio is None:
            continue

        summary = compute_portfolio_summary(portfolio)
        bot_last_cycle = last_cycle.get(bot.key, {})
        bot_training = training.get(bot.key, {})

        coins = []
        for symbol in TRACKED_SYMBOLS:
            position = portfolio.positions.get(symbol)
            record = bot_last_cycle.get(symbol)
            base_amount = position.base_amount if position else 0.0
            average_entry_price = position.average_entry_price if position else 0.0
            last_price = record["price"] if record else None
            unrealized_pnl = (
                (last_price - average_entry_price) * base_amount if record and base_amount > 0 else 0.0
            )

            coins.append(
                {
                    "symbol": symbol,
                    "price": last_price,
                    "week_change_pct": record["week_change_pct"] if record else None,
                    "base_amount": base_amount,
                    "average_entry_price": average_entry_price,
                    "unrealized_pnl": unrealized_pnl,
                    "action": record["action"] if record else None,
                    "reason": record["reason"] if record else None,
                    "evaluated_at": record["timestamp"] if record else None,
                    "training": bot_training.get(symbol),
                }
            )

        bots_payload.append(
            {
                "key": bot.key,
                "name": bot.name,
                "description": bot.description,
                "stop_loss_pct": bot.stop_loss_pct,
                "take_profit_pct": bot.take_profit_pct,
                "trailing_stop_pct": bot.trailing_stop_pct,
                "starting_balance": portfolio.starting_quote_balance,
                "cash": portfolio.quote_balance,
                "market_value": summary["market_value"],
                "equity": summary["equity"],
                "pnl": summary["pnl"],
                "pnl_pct": summary["pnl_pct"],
                "realized_pnl": portfolio.realized_pnl,
                "total_fees_paid": portfolio.total_fees_paid,
                "trade_count": len(portfolio.trade_log),
                "coins": coins,
                "recent_trades": [asdict(trade) for trade in reversed(portfolio.trade_log[-15:])],
                "equity_history": load_equity_history(ARENA_DIR / f"equity_{bot.key}.csv"),
            }
        )

    return jsonify(
        {
            "arena_active": True,
            "session": {
                "run_id": run_state.run_id,
                "started_at": run_state.started_at,
                "cycle_count": run_state.cycle_count,
                "completed": run_state.completed,
                "duration_hours": run_state.duration_hours,
                "interval_seconds": run_state.interval_seconds,
                "remaining_seconds": remaining_seconds(run_state, now),
            },
            "live_prices": live_prices,
            "bots": bots_payload,
            "recent_log": recent_log,
        }
    )


def _load_json(path):
    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _fetch_live_prices(symbols):
    prices = {}

    for symbol in symbols:
        try:
            prices[symbol] = get_live_price(symbol)
        except Exception:
            prices[symbol] = None

    return prices


def _coin_payload(symbol, portfolio, last_cycle):
    position = portfolio.positions.get(symbol)
    record = last_cycle.get(symbol)

    base_amount = position.base_amount if position else 0.0
    average_entry_price = position.average_entry_price if position else 0.0
    last_price = record.price if record else None
    unrealized_pnl = (last_price - average_entry_price) * base_amount if record and base_amount > 0 else 0.0

    return {
        "symbol": symbol,
        "price": last_price,
        "week_change_pct": record.week_change_pct if record else None,
        "base_amount": base_amount,
        "average_entry_price": average_entry_price,
        "unrealized_pnl": unrealized_pnl,
        "decision_action": record.decision_action if record else None,
        "decision_confidence": record.decision_confidence if record else None,
        "decision_reasoning": record.decision_reasoning if record else None,
        "plan_allowed": record.plan_allowed if record else None,
        "plan_side": record.plan_side if record else None,
        "evaluated_at": record.timestamp if record else None,
    }


def _tail_log(path, max_lines):
    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    return [line.rstrip("\n") for line in lines[-max_lines:]]


def run_web_monitor():
    app.run(host=WEB_MONITOR_HOST, port=WEB_MONITOR_PORT, debug=False)


if __name__ == "__main__":
    run_web_monitor()
