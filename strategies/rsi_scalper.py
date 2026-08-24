from dataclasses import dataclass

from config.settings import (
    MARKET_MOOD_BUY_THRESHOLD,
    MARKET_MOOD_SELL_THRESHOLD,
    MIN_SCALP_CONFIDENCE,
)
from strategies.market_models import ModelVote, analyze_weekly_trend_model, run_market_models


@dataclass(frozen=True)
class StrategySignal:
    action: str
    confidence: float
    price: float
    rsi: float
    mood_score: float
    scalp_possible: bool
    reason: str
    votes: tuple[ModelVote, ...]


def generate_scalping_signal(df, weekly_context=None):
    latest = df.iloc[-1]
    price = float(latest["Close"])
    rsi = float(latest["RSI"])
    votes = run_market_models(df)

    if weekly_context is not None:
        votes.append(analyze_weekly_trend_model(weekly_context))

    votes = tuple(votes)
    mood_score = _weighted_mood_score(votes)
    confidence = _confidence_from_votes(votes, mood_score)
    action = _action_from_mood(mood_score, confidence)
    scalp_possible = action != "HOLD" and confidence >= MIN_SCALP_CONFIDENCE
    reason = _build_reason(action, scalp_possible, confidence, mood_score, votes)

    return StrategySignal(
        action=action if scalp_possible else "HOLD",
        confidence=confidence,
        price=price,
        rsi=rsi,
        mood_score=mood_score,
        scalp_possible=scalp_possible,
        reason=reason,
        votes=votes,
    )


def generate_rsi_scalping_signal(df):
    return generate_scalping_signal(df)


def _weighted_mood_score(votes):
    weights = {
        "RSI": 1.35,
        "EMA Trend": 1.15,
        "Volume": 1.0,
        "Volatility": 1.2,
        "Price Action": 0.9,
        "Weekly Trend": 1.1,
    }
    total_weight = 0.0
    weighted_score = 0.0

    for vote in votes:
        weight = weights.get(vote.name, 1.0)
        weighted_score += vote.score * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0

    return max(min(weighted_score / total_weight, 1.0), -1.0)


def _confidence_from_votes(votes, mood_score):
    supportive_votes = sum(1 for vote in votes if _supports_mood(vote, mood_score))
    confidence = abs(mood_score) * 0.65 + (supportive_votes / len(votes)) * 0.35
    return max(min(confidence, 0.95), 0.0)


def _supports_mood(vote, mood_score):
    if mood_score > 0:
        return vote.score > 0

    if mood_score < 0:
        return vote.score < 0

    return vote.bias == "HOLD"


def _action_from_mood(mood_score, confidence):
    if mood_score >= MARKET_MOOD_BUY_THRESHOLD and confidence >= MIN_SCALP_CONFIDENCE:
        return "BUY"

    if mood_score <= MARKET_MOOD_SELL_THRESHOLD and confidence >= MIN_SCALP_CONFIDENCE:
        return "SELL"

    return "HOLD"


def _build_reason(action, scalp_possible, confidence, mood_score, votes):
    strongest = sorted(votes, key=lambda vote: abs(vote.score), reverse=True)[:2]
    factor_summary = "; ".join(vote.detail for vote in strongest)

    if scalp_possible:
        return (
            f"Market mood supports {action} scalping "
            f"(score {mood_score:.2f}, confidence {confidence:.0%}). {factor_summary}"
        )

    return (
        f"Scalping is not favorable yet "
        f"(score {mood_score:.2f}, confidence {confidence:.0%}). {factor_summary}"
    )
