import time
from datetime import datetime, timezone

from config.settings import (
    SESSION_DURATION_HOURS,
    SESSION_INTERVAL_SECONDS,
    SESSION_STARTING_QUOTE_BALANCE,
    STATE_DIR,
    TRACKED_SYMBOLS,
)
from engine.equity_history import append_equity_snapshot
from engine.last_cycle import load_last_cycle, save_last_cycle
from engine.session_state import (
    is_expired,
    load_run_state,
    new_run_state,
    remaining_seconds,
    save_run_state,
)
from engine.trading_engine import evaluate_symbol
from portfolio.persistence import load_portfolio_state, save_portfolio_state
from portfolio.portfolio_state import new_portfolio
from portfolio.valuation import compute_portfolio_summary
from reporting.session_report import generate_report
from utils.logger import get_logger

RUN_STATE_PATH = STATE_DIR / "run_state.json"
PORTFOLIO_STATE_PATH = STATE_DIR / "portfolio_state.json"
LAST_CYCLE_PATH = STATE_DIR / "last_cycle.json"
EQUITY_HISTORY_PATH = STATE_DIR / "equity_history.csv"

logger = get_logger()


def run_multi_coin_session():
    now = datetime.now(timezone.utc)

    run_state = load_run_state(RUN_STATE_PATH)
    portfolio = load_portfolio_state(PORTFOLIO_STATE_PATH)
    last_cycle_records = load_last_cycle(LAST_CYCLE_PATH)

    if run_state is None or run_state.completed or is_expired(run_state, now):
        if run_state is not None and not run_state.completed:
            logger.info("Previous session expired without being finalized. Generating its report first.")
            generate_report(portfolio, run_state)

        logger.info("Starting a new %.0fh multi-coin session for %s", SESSION_DURATION_HOURS, TRACKED_SYMBOLS)
        run_state = new_run_state(TRACKED_SYMBOLS, SESSION_DURATION_HOURS, SESSION_INTERVAL_SECONDS, now)
        portfolio = new_portfolio(TRACKED_SYMBOLS, SESSION_STARTING_QUOTE_BALANCE)
        last_cycle_records = {}
        save_run_state(run_state, RUN_STATE_PATH)
        save_portfolio_state(portfolio, PORTFOLIO_STATE_PATH)
        save_last_cycle(last_cycle_records, LAST_CYCLE_PATH)
    else:
        if run_state.interval_seconds != SESSION_INTERVAL_SECONDS:
            logger.info(
                "Interval changed in config: %ss -> %ss. Applying to the resumed session.",
                run_state.interval_seconds,
                SESSION_INTERVAL_SECONDS,
            )
            run_state.interval_seconds = SESSION_INTERVAL_SECONDS
            save_run_state(run_state, RUN_STATE_PATH)

        if run_state.duration_hours != SESSION_DURATION_HOURS:
            logger.info(
                "Duration changed in config: %.1fh -> %.1fh. Applying to the resumed session.",
                run_state.duration_hours,
                SESSION_DURATION_HOURS,
            )
            run_state.duration_hours = SESSION_DURATION_HOURS
            save_run_state(run_state, RUN_STATE_PATH)

        logger.info(
            "Resuming session %s | cycle %s | %.1f minutes remaining",
            run_state.run_id,
            run_state.cycle_count,
            remaining_seconds(run_state, now) / 60,
        )

    while True:
        now = datetime.now(timezone.utc)

        if is_expired(run_state, now):
            run_state.completed = True
            save_run_state(run_state, RUN_STATE_PATH)
            logger.info("Session duration reached. Finalizing report.")
            generate_report(portfolio, run_state)
            break

        run_state.cycle_count += 1
        logger.info(
            "Cycle %s starting | %.1f minutes remaining",
            run_state.cycle_count,
            remaining_seconds(run_state, now) / 60,
        )

        for symbol in run_state.symbols:
            try:
                record = evaluate_symbol(symbol, portfolio, now.isoformat())
                last_cycle_records[symbol] = record
                logger.info(
                    "%s | price=$%.4f | week=%+.2f%% | %s=%s (%.0f%%) | plan=%s(%s) | reason=%s",
                    record.symbol,
                    record.price,
                    record.week_change_pct,
                    record.decision_engine,
                    record.decision_action,
                    record.decision_confidence * 100,
                    record.plan_side,
                    "ALLOWED" if record.plan_allowed else "BLOCKED",
                    record.decision_reasoning,
                )
            except Exception:
                logger.exception("Cycle failed for %s, skipping this coin this cycle.", symbol)

            run_state.last_cycle_at = now.isoformat()
            save_run_state(run_state, RUN_STATE_PATH)
            save_portfolio_state(portfolio, PORTFOLIO_STATE_PATH)
            save_last_cycle(last_cycle_records, LAST_CYCLE_PATH)

        try:
            summary = compute_portfolio_summary(portfolio)
            append_equity_snapshot(
                EQUITY_HISTORY_PATH,
                {
                    "timestamp": now.isoformat(),
                    "cycle": run_state.cycle_count,
                    "cash": round(portfolio.quote_balance, 4),
                    "market_value": round(summary["market_value"], 4),
                    "equity": round(summary["equity"], 4),
                    "realized_pnl": round(portfolio.realized_pnl, 4),
                    "fees_paid": round(portfolio.total_fees_paid, 4),
                    "pnl_pct": round(summary["pnl_pct"], 4),
                },
            )
        except Exception:
            logger.exception("Failed to record equity snapshot for cycle %s.", run_state.cycle_count)

        sleep_seconds = min(run_state.interval_seconds, remaining_seconds(run_state, datetime.now(timezone.utc)))

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return run_state, portfolio
