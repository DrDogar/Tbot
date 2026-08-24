from dataclasses import dataclass

from config.settings import EMA_FAST, EMA_SLOW


@dataclass(frozen=True)
class EntrySignal:
    should_enter: bool
    confidence: float
    reason: str


def momentum_rider_entry(df, weekly_context):
    if len(df) < EMA_SLOW + 2:
        return EntrySignal(False, 0.0, "Not enough data.")

    closes = df["Close"]
    fast = closes.ewm(span=EMA_FAST, adjust=False).mean().iloc[-1]
    slow = closes.ewm(span=EMA_SLOW, adjust=False).mean().iloc[-1]
    latest = df.iloc[-1]
    price = float(latest["Close"])
    open_price = float(latest["Open"])
    high = float(latest["High"])
    low = float(latest["Low"])
    candle_range = high - low

    if price <= 0 or slow <= 0 or candle_range <= 0:
        return EntrySignal(False, 0.0, "Not enough range data.")

    spread_pct = ((fast - slow) / price) * 100
    strong_candle = price > open_price and ((price - low) / candle_range) >= 0.6

    if spread_pct > 0.05 and strong_candle:
        confidence = min(spread_pct / 0.3, 1.0)
        return EntrySignal(True, confidence, f"Uptrend confirmed (EMA spread {spread_pct:.3f}%) with a strong bullish candle.")

    return EntrySignal(False, 0.0, "No confirmed wave yet.")


def scalper_entry(df, weekly_context):
    if len(df) < 3 or "RSI" not in df.columns:
        return EntrySignal(False, 0.0, "Not enough data.")

    latest = df.iloc[-1]
    rsi = float(latest["RSI"])
    price = float(latest["Close"])
    open_price = float(latest["Open"])
    low = float(latest["Low"])
    high = float(latest["High"])
    candle_range = high - low

    if candle_range <= 0:
        return EntrySignal(False, 0.0, "Flat candle.")

    bullish_reversal = price > open_price and ((price - low) / candle_range) >= 0.55

    if rsi < 45 and bullish_reversal:
        confidence = min((45 - rsi) / 25 + 0.3, 1.0)
        return EntrySignal(True, confidence, f"RSI {rsi:.1f} dip with a bullish reversal candle.")

    return EntrySignal(False, 0.0, "No quick scalp setup.")


def breakout_entry(df, weekly_context, lookback=20):
    if len(df) < lookback + 1:
        return EntrySignal(False, 0.0, "Not enough data.")

    recent = df.iloc[-(lookback + 1) : -1]
    latest = df.iloc[-1]
    price = float(latest["Close"])
    prior_high = float(recent["High"].max())
    avg_volume = float(recent["Volume"].mean())
    latest_volume = float(latest["Volume"])

    if prior_high <= 0 or avg_volume <= 0:
        return EntrySignal(False, 0.0, "Not enough range data.")

    breakout_pct = ((price - prior_high) / prior_high) * 100
    volume_ratio = latest_volume / avg_volume

    if breakout_pct > 0 and volume_ratio >= 1.2:
        confidence = min(breakout_pct / 0.3 + volume_ratio / 5, 1.0)
        return EntrySignal(True, confidence, f"Broke above {lookback}-candle high by {breakout_pct:.3f}% on {volume_ratio:.2f}x volume.")

    return EntrySignal(False, 0.0, "No breakout yet.")


def trend_follower_entry(df, weekly_context):
    if weekly_context is None or not weekly_context.get("data_available"):
        return EntrySignal(False, 0.0, "No weekly trend data.")

    week_change_pct = weekly_context["week_change_pct"]

    if week_change_pct < 1.5:
        return EntrySignal(False, 0.0, f"Weekly trend not strong enough ({week_change_pct:+.2f}%).")

    if len(df) < EMA_SLOW + 1 or "RSI" not in df.columns:
        return EntrySignal(False, 0.0, "Not enough data.")

    latest = df.iloc[-1]
    rsi = float(latest["RSI"])
    price = float(latest["Close"])
    slow = df["Close"].ewm(span=EMA_SLOW, adjust=False).mean().iloc[-1]

    if 35 <= rsi <= 60 and price >= slow:
        confidence = min(week_change_pct / 5.0, 1.0)
        return EntrySignal(True, confidence, f"Riding the {week_change_pct:+.2f}% weekly uptrend on a pullback (RSI {rsi:.1f}).")

    return EntrySignal(False, 0.0, "Waiting for a pullback within the weekly uptrend.")


def aggressive_voter_entry(df, weekly_context):
    from strategies.rsi_scalper import generate_scalping_signal

    signal = generate_scalping_signal(df, weekly_context=weekly_context)

    if signal.action == "BUY":
        return EntrySignal(True, signal.confidence, signal.reason)

    return EntrySignal(False, signal.confidence, signal.reason)
