from dataclasses import dataclass, replace

from ai.claude_advisor import TradeDecision, ask_trade_decision
from config.settings import (
    DECISION_ENGINE,
    DEFAULT_LIMIT,
    DEFAULT_TIMEFRAME,
    SESSION_TRADE_QUOTE_AMOUNT,
    TAKER_FEE_PCT,
    WEEKLY_TIMEFRAME,
)
from data.collector import get_last_week_market_data, get_market_data
from indicators.rsi import calculate_rsi
from portfolio.portfolio_state import apply_fill, get_position
from risk.spot_guard import SpotAccountSnapshot, build_spot_trade_plan
from strategies.rsi_scalper import generate_scalping_signal
from strategies.weekly_context import summarize_weekly_context


@dataclass(frozen=True)
class CycleRecord:
    symbol: str
    timestamp: str
    price: float
    week_change_pct: float
    decision_engine: str
    decision_action: str
    decision_confidence: float
    decision_reasoning: str
    internal_action: str
    plan_allowed: bool
    plan_side: str
    plan_reason: str


def evaluate_symbol(symbol, portfolio, timestamp):
    weekly_df = get_last_week_market_data(symbol, timeframe=WEEKLY_TIMEFRAME)
    weekly_context = summarize_weekly_context(weekly_df)

    current_df = calculate_rsi(get_market_data(symbol, timeframe=DEFAULT_TIMEFRAME, limit=DEFAULT_LIMIT))
    signal = generate_scalping_signal(current_df, weekly_context=weekly_context)

    position = get_position(portfolio, symbol)
    position_payload = {
        "holding": position.base_amount > 0,
        "base_amount": round(position.base_amount, 8),
        "average_entry_price": round(position.average_entry_price, 4),
    }

    round_trip_fee_pct = TAKER_FEE_PCT * 2

    if DECISION_ENGINE == "claude":
        decision = ask_trade_decision(
            symbol=symbol,
            weekly_summary=weekly_context,
            current_signal=_signal_to_payload(signal),
            position=position_payload,
            round_trip_fee_pct=round_trip_fee_pct,
        )
    else:
        decision = TradeDecision(
            action=signal.action,
            confidence=signal.confidence,
            reasoning=signal.reason,
        )

    decision_signal = replace(
        signal,
        action=decision.action,
        confidence=decision.confidence,
        reason=decision.reasoning,
    )

    account = SpotAccountSnapshot(base_free=position.base_amount, quote_free=portfolio.quote_balance)
    plan = build_spot_trade_plan(
        decision_signal,
        symbol,
        account=account,
        quote_amount=SESSION_TRADE_QUOTE_AMOUNT,
        fee_pct=TAKER_FEE_PCT,
    )

    if plan.allowed:
        apply_fill(portfolio, symbol, plan, timestamp)

    return CycleRecord(
        symbol=symbol,
        timestamp=timestamp,
        price=signal.price,
        week_change_pct=weekly_context.get("week_change_pct", 0.0),
        decision_engine=DECISION_ENGINE,
        decision_action=decision.action,
        decision_confidence=decision.confidence,
        decision_reasoning=decision.reasoning,
        internal_action=signal.action,
        plan_allowed=plan.allowed,
        plan_side=plan.side,
        plan_reason=plan.reason,
    )


def _signal_to_payload(signal):
    return {
        "price": signal.price,
        "rsi": round(signal.rsi, 2),
        "mood_score": round(signal.mood_score, 3),
        "scalp_possible": signal.scalp_possible,
        "internal_model_action": signal.action,
        "internal_model_confidence": round(signal.confidence, 3),
        "votes": [
            {"name": vote.name, "bias": vote.bias, "score": round(vote.score, 3), "detail": vote.detail}
            for vote in signal.votes
        ],
    }
