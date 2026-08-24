import json
import time
from datetime import datetime, timezone

from bots.bot_configs import BOTS
from bots.engine import evaluate_symbol_for_all_bots
from bots.ensemble_model import build_stacked_dataset
from bots.forest_model import load_all_forests, save_all_forests, train_forest
from bots.neural_model import (
    MIN_TRAINING_SAMPLES,
    build_training_dataset,
    load_all_weights,
    save_all_weights,
    train_network,
)
from bots.trainer import train_bot_on_symbol
from bots.trend_ai_model import (
    EPOCHS as TREND_EPOCHS,
    HIDDEN_UNITS as TREND_HIDDEN_UNITS,
    LEARNING_RATE as TREND_LEARNING_RATE,
    build_long_training_dataset,
)
from config.settings import (
    NEURAL_TRAINING_LOOKBACK_DAYS,
    NEURAL_TRAINING_TIMEFRAME,
    SESSION_DURATION_HOURS,
    SESSION_INTERVAL_SECONDS,
    STATE_DIR,
    TRACKED_SYMBOLS,
)
from data.collector import get_last_year_market_data
from engine.equity_history import append_equity_snapshot
from engine.session_state import (
    is_expired,
    load_run_state,
    new_run_state,
    remaining_seconds,
    save_run_state,
)
from portfolio.persistence import load_portfolio_state, save_portfolio_state
from portfolio.portfolio_state import new_portfolio
from portfolio.valuation import compute_portfolio_summary
from reporting.arena_report import generate_arena_report
from utils.logger import get_logger

ARENA_DIR = STATE_DIR / "bots"
RUN_STATE_PATH = ARENA_DIR / "run_state.json"
TRAINING_PATH = ARENA_DIR / "training.json"
LAST_CYCLE_PATH = ARENA_DIR / "last_cycle.json"
NEURAL_WEIGHTS_PATH = ARENA_DIR / "neural_weights.json"
FOREST_WEIGHTS_PATH = ARENA_DIR / "forest_weights.json"
ENSEMBLE_WEIGHTS_PATH = ARENA_DIR / "ensemble_weights.json"
TREND_WEIGHTS_PATH = ARENA_DIR / "trend_ai_weights.json"

logger = get_logger()


def _portfolio_path(bot_key):
    return ARENA_DIR / f"portfolio_{bot_key}.json"


def _equity_path(bot_key):
    return ARENA_DIR / f"equity_{bot_key}.csv"


def _save_json(payload, path):
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


def _load_json(path):
    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _run_training():
    logger.info("Training all bots on the last %d days of data for each coin...", NEURAL_TRAINING_LOOKBACK_DAYS)
    training = {}
    neural_weights = {}
    forest_models = {}
    ensemble_weights = {}
    trend_weights = {}

    for symbol in TRACKED_SYMBOLS:
        logger.info(
            "Fetching last %d days of %s data for %s (this can take a minute)...",
            NEURAL_TRAINING_LOOKBACK_DAYS,
            NEURAL_TRAINING_TIMEFRAME,
            symbol,
        )
        year_df = get_last_year_market_data(
            symbol, timeframe=NEURAL_TRAINING_TIMEFRAME, lookback_days=NEURAL_TRAINING_LOOKBACK_DAYS
        )

        for bot in BOTS:
            if bot.uses_neural_net or bot.uses_forest or bot.uses_ensemble or bot.uses_trend_ai:
                continue

            result = train_bot_on_symbol(bot, symbol, year_df)
            training.setdefault(bot.key, {})[symbol] = {
                "trades": result.trades,
                "win_rate": result.win_rate,
                "total_return_pct": result.total_return_pct,
            }
            logger.info(
                "Trained %s on %s | trades=%d win_rate=%.0f%% return=%+.2f%%",
                bot.name,
                symbol,
                result.trades,
                result.win_rate * 100,
                result.total_return_pct,
            )

        # Both AI models train off the same engineered features/labels, so build that
        # dataset once per symbol instead of twice (it's the expensive part).
        features, labels = build_training_dataset(year_df)

        if len(features) < MIN_TRAINING_SAMPLES:
            neural_weights[symbol] = None
            forest_models[symbol] = None
            ensemble_weights[symbol] = None
            trend_weights[symbol] = None
            logger.info("Not enough data to train AI models on %s | %d rows.", symbol, len(year_df))
            continue

        neural_weights[symbol] = train_network(features, labels)
        logger.info(
            "Trained Neural Net Trader on %s | %d rows | %d samples | converged", symbol, len(year_df), len(features)
        )

        forest_models[symbol] = train_forest(features, labels)
        logger.info(
            "Trained Random Forest Trader on %s | %d rows | %d samples | converged",
            symbol,
            len(year_df),
            len(features),
        )

        # The ensemble learns from what the two models above already predict at each
        # bar, so it has to train after both of them are ready for this symbol.
        stacked_features, stacked_labels = build_stacked_dataset(year_df, neural_weights[symbol], forest_models[symbol])

        if len(stacked_features) < MIN_TRAINING_SAMPLES:
            ensemble_weights[symbol] = None
            logger.info("Not enough data to train Ensemble Meta-Trader on %s.", symbol)
        else:
            ensemble_weights[symbol] = train_network(stacked_features, stacked_labels)
            logger.info(
                "Trained Ensemble Meta-Trader on %s | %d rows | %d samples | converged",
                symbol,
                len(year_df),
                len(stacked_features),
            )

        # Patient Trend AI trains on its own longer-horizon dataset (3-day lookahead,
        # 30-day regime feature), built from the same year_df but sliced differently.
        trend_features, trend_labels = build_long_training_dataset(year_df)

        if len(trend_features) < MIN_TRAINING_SAMPLES:
            trend_weights[symbol] = None
            logger.info("Not enough data to train Patient Trend AI on %s.", symbol)
        else:
            trend_weights[symbol] = train_network(
                trend_features, trend_labels, hidden_dim=TREND_HIDDEN_UNITS, epochs=TREND_EPOCHS, lr=TREND_LEARNING_RATE
            )
            logger.info(
                "Trained Patient Trend AI on %s | %d rows | %d samples | converged",
                symbol,
                len(year_df),
                len(trend_features),
            )

    return training, neural_weights, forest_models, ensemble_weights, trend_weights


def _run_training_with_retry(max_attempts=3, backoff_seconds=30):
    for attempt in range(1, max_attempts + 1):
        try:
            return _run_training()
        except Exception:
            if attempt == max_attempts:
                raise

            logger.exception(
                "Training failed (attempt %d/%d), likely a network blip. Retrying in %ds...",
                attempt,
                max_attempts,
                backoff_seconds,
            )
            time.sleep(backoff_seconds)


def run_bot_arena():
    now = datetime.now(timezone.utc)

    run_state = load_run_state(RUN_STATE_PATH)
    training = _load_json(TRAINING_PATH)
    neural_weights = load_all_weights(NEURAL_WEIGHTS_PATH)
    forest_models = load_all_forests(FOREST_WEIGHTS_PATH)
    ensemble_weights = load_all_weights(ENSEMBLE_WEIGHTS_PATH)
    trend_weights = load_all_weights(TREND_WEIGHTS_PATH)
    portfolios = {bot.key: load_portfolio_state(_portfolio_path(bot.key)) for bot in BOTS}
    last_cycle = _load_json(LAST_CYCLE_PATH) or {}

    fresh_start = run_state is None or run_state.completed or is_expired(run_state, now)

    if fresh_start:
        if run_state is not None and not run_state.completed and any(portfolios.values()):
            logger.info("Previous arena session expired without being finalized. Generating its report first.")
            generate_arena_report(BOTS, portfolios, run_state)

        logger.info("Starting a new %.0fh, %d-bot arena across %s", SESSION_DURATION_HOURS, len(BOTS), TRACKED_SYMBOLS)
        training, neural_weights, forest_models, ensemble_weights, trend_weights = _run_training_with_retry()
        _save_json(training, TRAINING_PATH)
        save_all_weights(neural_weights, NEURAL_WEIGHTS_PATH)
        save_all_forests(forest_models, FOREST_WEIGHTS_PATH)
        save_all_weights(ensemble_weights, ENSEMBLE_WEIGHTS_PATH)
        save_all_weights(trend_weights, TREND_WEIGHTS_PATH)

        run_state = new_run_state(TRACKED_SYMBOLS, SESSION_DURATION_HOURS, SESSION_INTERVAL_SECONDS, now)
        portfolios = {bot.key: new_portfolio(TRACKED_SYMBOLS, bot.starting_quote_balance) for bot in BOTS}
        last_cycle = {}

        save_run_state(run_state, RUN_STATE_PATH)

        for bot in BOTS:
            save_portfolio_state(portfolios[bot.key], _portfolio_path(bot.key))

        _save_json(last_cycle, LAST_CYCLE_PATH)
    else:
        for bot in BOTS:
            if portfolios[bot.key] is None:
                logger.info("New bot '%s' joined an in-progress arena. Starting it with a fresh $%.2f.", bot.name, bot.starting_quote_balance)
                portfolios[bot.key] = new_portfolio(TRACKED_SYMBOLS, bot.starting_quote_balance)
                save_portfolio_state(portfolios[bot.key], _portfolio_path(bot.key))

        if run_state.interval_seconds != SESSION_INTERVAL_SECONDS:
            logger.info(
                "Interval changed in config: %ss -> %ss. Applying to the resumed arena.",
                run_state.interval_seconds,
                SESSION_INTERVAL_SECONDS,
            )
            run_state.interval_seconds = SESSION_INTERVAL_SECONDS
            save_run_state(run_state, RUN_STATE_PATH)

        if run_state.duration_hours != SESSION_DURATION_HOURS:
            logger.info(
                "Duration changed in config: %.1fh -> %.1fh. Applying to the resumed arena.",
                run_state.duration_hours,
                SESSION_DURATION_HOURS,
            )
            run_state.duration_hours = SESSION_DURATION_HOURS
            save_run_state(run_state, RUN_STATE_PATH)

        if training is None or not neural_weights or not forest_models or not ensemble_weights or not trend_weights:
            try:
                training, neural_weights, forest_models, ensemble_weights, trend_weights = _run_training_with_retry()
                _save_json(training, TRAINING_PATH)
                save_all_weights(neural_weights, NEURAL_WEIGHTS_PATH)
                save_all_forests(forest_models, FOREST_WEIGHTS_PATH)
                save_all_weights(ensemble_weights, ENSEMBLE_WEIGHTS_PATH)
                save_all_weights(trend_weights, TREND_WEIGHTS_PATH)
            except Exception:
                # Don't let a stubborn network blip kill a resumed arena that already has
                # hours of progress. Fall back to whatever training/weights exist (possibly
                # none) -- affected bots just stay flat until the next retrain opportunity.
                logger.exception("Retraining failed after retries. Resuming with existing training/weights.")
                training = training or {}
                neural_weights = neural_weights or {}
                forest_models = forest_models or {}
                ensemble_weights = ensemble_weights or {}
                trend_weights = trend_weights or {}

        logger.info(
            "Resuming arena %s | cycle %s | %.1f minutes remaining",
            run_state.run_id,
            run_state.cycle_count,
            remaining_seconds(run_state, now) / 60,
        )

    while True:
        now = datetime.now(timezone.utc)

        if is_expired(run_state, now):
            run_state.completed = True
            save_run_state(run_state, RUN_STATE_PATH)
            logger.info("Arena duration reached. Finalizing report.")
            generate_arena_report(BOTS, portfolios, run_state)
            break

        run_state.cycle_count += 1
        logger.info(
            "Arena cycle %s starting | %.1f minutes remaining",
            run_state.cycle_count,
            remaining_seconds(run_state, now) / 60,
        )

        for symbol in run_state.symbols:
            try:
                symbol_records = evaluate_symbol_for_all_bots(
                    symbol,
                    BOTS,
                    portfolios,
                    training,
                    neural_weights,
                    forest_models,
                    ensemble_weights,
                    trend_weights,
                    now.isoformat(),
                )

                for bot_key, record in symbol_records.items():
                    last_cycle.setdefault(bot_key, {})[symbol] = record

                    if record["action"] != "HOLD":
                        logger.info(
                            "[%s] %s %s @ $%.4f | %s",
                            bot_key,
                            symbol,
                            record["action"],
                            record["price"],
                            record["reason"],
                        )
            except Exception:
                logger.exception("Arena cycle failed for %s, skipping this coin this cycle.", symbol)

            run_state.last_cycle_at = now.isoformat()
            save_run_state(run_state, RUN_STATE_PATH)

            for bot in BOTS:
                save_portfolio_state(portfolios[bot.key], _portfolio_path(bot.key))

            _save_json(last_cycle, LAST_CYCLE_PATH)

        for bot in BOTS:
            try:
                summary = compute_portfolio_summary(portfolios[bot.key])
                append_equity_snapshot(
                    _equity_path(bot.key),
                    {
                        "timestamp": now.isoformat(),
                        "cycle": run_state.cycle_count,
                        "cash": round(portfolios[bot.key].quote_balance, 4),
                        "market_value": round(summary["market_value"], 4),
                        "equity": round(summary["equity"], 4),
                        "realized_pnl": round(portfolios[bot.key].realized_pnl, 4),
                        "fees_paid": round(portfolios[bot.key].total_fees_paid, 4),
                        "pnl_pct": round(summary["pnl_pct"], 4),
                    },
                )
            except Exception:
                logger.exception("Failed to record equity snapshot for %s cycle %s.", bot.key, run_state.cycle_count)

        sleep_seconds = min(run_state.interval_seconds, remaining_seconds(run_state, datetime.now(timezone.utc)))

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return run_state, portfolios
