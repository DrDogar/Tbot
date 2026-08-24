from dataclasses import dataclass

from bots.ensemble_model import stacked_feature_vector
from bots.entry_strategies import EntrySignal
from bots.forest_model import predict as forest_predict
from bots.neural_model import feature_vector, predict as neural_predict
from bots.position_manager import check_exit
from bots.position_sizing import size_position
from bots.trainer import is_coin_allowed_for_bot
from bots.trend_ai_model import regime_feature_vector
from config.settings import (
    DEFAULT_LIMIT,
    DEFAULT_TIMEFRAME,
    REGIME_LOOKBACK_DAYS,
    REGIME_TIMEFRAME,
    TAKER_FEE_PCT,
    WEEKLY_TIMEFRAME,
)
from data.collector import get_last_week_market_data, get_market_data, get_regime_market_data
from indicators.rsi import calculate_rsi
from portfolio.portfolio_state import apply_fill, get_position
from risk.spot_guard import SpotAccountSnapshot, build_spot_trade_plan
from strategies.weekly_context import summarize_weekly_context


@dataclass(frozen=True)
class ArenaSignal:
    action: str
    price: float
    reason: str


def evaluate_symbol_for_all_bots(
    symbol, bots, portfolios, training, neural_weights, forest_models, ensemble_weights, trend_weights, timestamp
):
    weekly_df = get_last_week_market_data(symbol, timeframe=WEEKLY_TIMEFRAME)
    weekly_context = summarize_weekly_context(weekly_df)

    regime_df = get_regime_market_data(symbol, timeframe=REGIME_TIMEFRAME, lookback_days=REGIME_LOOKBACK_DAYS)
    regime_context = summarize_weekly_context(regime_df)

    current_df = calculate_rsi(get_market_data(symbol, timeframe=DEFAULT_TIMEFRAME, limit=DEFAULT_LIMIT))
    price = float(current_df.iloc[-1]["Close"])
    week_change_pct = weekly_context.get("week_change_pct", 0.0)

    records = {}

    for bot in bots:
        try:
            action_taken, reason = _evaluate_one_bot(
                bot,
                symbol,
                portfolios[bot.key],
                training,
                neural_weights,
                forest_models,
                ensemble_weights,
                trend_weights,
                current_df,
                weekly_context,
                regime_context,
                price,
                timestamp,
            )
        except Exception as error:
            action_taken, reason = "HOLD", f"Skipped this cycle due to an internal error: {error}"

        records[bot.key] = {
            "symbol": symbol,
            "timestamp": timestamp,
            "price": price,
            "week_change_pct": week_change_pct,
            "action": action_taken,
            "reason": reason,
        }

    return records


def _evaluate_one_bot(
    bot,
    symbol,
    portfolio,
    training,
    neural_weights,
    forest_models,
    ensemble_weights,
    trend_weights,
    current_df,
    weekly_context,
    regime_context,
    price,
    timestamp,
):
    position = get_position(portfolio, symbol)

    if position.base_amount > 0:
        position.peak_price = max(position.peak_price, price)
        exit_decision = check_exit(bot, position, price)

        if not exit_decision.should_exit:
            return "HOLD", ""

        sell_signal = ArenaSignal("SELL", price, exit_decision.reason)
        account = SpotAccountSnapshot(base_free=position.base_amount, quote_free=portfolio.quote_balance)
        # Size the exit off the full position value so a stop-loss/take-profit always closes
        # the whole position, however many chunks it was built from.
        full_exit_quote_amount = position.base_amount * price
        plan = build_spot_trade_plan(
            sell_signal, symbol, account=account, quote_amount=full_exit_quote_amount, fee_pct=TAKER_FEE_PCT
        )

        if plan.allowed:
            apply_fill(portfolio, symbol, plan, timestamp)
            return "SELL", exit_decision.reason

        return "HOLD", ""

    entry_signal = _get_entry_signal(
        bot,
        symbol,
        current_df,
        weekly_context,
        regime_context,
        training,
        neural_weights,
        forest_models,
        ensemble_weights,
        trend_weights,
    )

    if not entry_signal.should_enter:
        return "HOLD", entry_signal.reason

    buy_signal = ArenaSignal("BUY", price, entry_signal.reason)
    account = SpotAccountSnapshot(base_free=0.0, quote_free=portfolio.quote_balance)
    # $100 chunks, scaled up with how confident the entry signal is (1-4 chunks).
    quote_amount = size_position(entry_signal.confidence)
    plan = build_spot_trade_plan(buy_signal, symbol, account=account, quote_amount=quote_amount, fee_pct=TAKER_FEE_PCT)

    if plan.allowed:
        apply_fill(portfolio, symbol, plan, timestamp)
        return "BUY", entry_signal.reason

    return "HOLD", entry_signal.reason


def _get_entry_signal(
    bot,
    symbol,
    current_df,
    weekly_context,
    regime_context,
    training,
    neural_weights,
    forest_models,
    ensemble_weights,
    trend_weights,
):
    if bot.uses_trend_ai:
        weights = trend_weights.get(symbol)

        if weights is None:
            return EntrySignal(False, 0.0, "Not enough historical data to train a trend model for this coin.")

        features = regime_feature_vector(current_df, weekly_context, regime_context)
        action, confidence = neural_predict(weights, features)

        if action == "BUY":
            return EntrySignal(
                True, confidence, f"Patient Trend AI sees a sustained uptrend forming ({confidence:.0%} confidence)."
            )

        return EntrySignal(False, confidence, f"Patient Trend AI says {action} -- no strong trend yet ({confidence:.0%}).")

    if bot.uses_ensemble:
        weights = neural_weights.get(symbol)
        forest = forest_models.get(symbol)
        ensemble_weights_for_symbol = ensemble_weights.get(symbol)

        if weights is None or forest is None or ensemble_weights_for_symbol is None:
            return EntrySignal(False, 0.0, "Not enough historical data to train an ensemble model for this coin.")

        stacked = stacked_feature_vector(current_df, weekly_context, weights, forest)
        action, confidence = neural_predict(ensemble_weights_for_symbol, stacked)

        if action == "BUY":
            return EntrySignal(
                True, confidence, f"Ensemble (stacked on neural net + forest) predicts BUY with {confidence:.0%} probability."
            )

        return EntrySignal(False, confidence, f"Ensemble predicts {action} ({confidence:.0%} probability).")

    if bot.uses_neural_net:
        weights = neural_weights.get(symbol)

        if weights is None:
            return EntrySignal(False, 0.0, "Not enough historical data to train a model for this coin.")

        features = feature_vector(current_df, weekly_context)
        action, confidence = neural_predict(weights, features)

        if action == "BUY":
            return EntrySignal(True, confidence, f"Neural net predicts BUY with {confidence:.0%} probability.")

        return EntrySignal(False, confidence, f"Neural net predicts {action} ({confidence:.0%} probability).")

    if bot.uses_forest:
        forest = forest_models.get(symbol)

        if forest is None:
            return EntrySignal(False, 0.0, "Not enough historical data to train a forest model for this coin.")

        features = feature_vector(current_df, weekly_context)
        action, confidence = forest_predict(forest, features)

        if action == "BUY":
            return EntrySignal(True, confidence, f"Random forest predicts BUY ({confidence:.0%} of trees agree).")

        return EntrySignal(False, confidence, f"Random forest predicts {action} ({confidence:.0%} of trees agree).")

    if not is_coin_allowed_for_bot(training, bot.key, symbol):
        return EntrySignal(False, 0.0, "Blocked by weekly training: this coin lost money in the backtest.")

    return bot.entry_fn(current_df, weekly_context)
