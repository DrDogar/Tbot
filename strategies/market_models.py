from dataclasses import dataclass

from config.settings import (
    EMA_FAST,
    EMA_SLOW,
    MAX_SCALP_VOLATILITY_PCT,
    MIN_SCALP_VOLATILITY_PCT,
    MIN_VOLUME_RATIO,
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
    VOLATILITY_LOOKBACK,
    VOLUME_LOOKBACK,
)


@dataclass(frozen=True)
class ModelVote:
    name: str
    bias: str
    score: float
    detail: str


def analyze_rsi_model(df):
    latest = df.iloc[-1]
    rsi = float(latest["RSI"])

    if rsi <= RSI_OVERSOLD:
        score = min((RSI_OVERSOLD - rsi) / 20 + 0.5, 1.0)
        return ModelVote("RSI", "BUY", score, f"RSI {rsi:.2f} is oversold.")

    if rsi >= RSI_OVERBOUGHT:
        score = -min((rsi - RSI_OVERBOUGHT) / 20 + 0.5, 1.0)
        return ModelVote("RSI", "SELL", score, f"RSI {rsi:.2f} is overbought.")

    return ModelVote("RSI", "HOLD", 0.0, f"RSI {rsi:.2f} is neutral.")


def analyze_ema_trend_model(df):
    closes = df["Close"]
    fast = closes.ewm(span=EMA_FAST, adjust=False).mean().iloc[-1]
    slow = closes.ewm(span=EMA_SLOW, adjust=False).mean().iloc[-1]
    price = float(closes.iloc[-1])

    if price <= 0:
        return ModelVote("EMA Trend", "HOLD", 0.0, "Price is unavailable.")

    spread_pct = ((fast - slow) / price) * 100
    score = max(min(spread_pct / 0.35, 1.0), -1.0)

    if score > 0.15:
        return ModelVote("EMA Trend", "BUY", score, f"Fast EMA is above slow EMA by {spread_pct:.3f}%.")

    if score < -0.15:
        return ModelVote("EMA Trend", "SELL", score, f"Fast EMA is below slow EMA by {abs(spread_pct):.3f}%.")

    return ModelVote("EMA Trend", "HOLD", 0.0, "EMA trend is flat.")


def analyze_volume_model(df):
    if "Volume" not in df.columns or len(df) < 2:
        return ModelVote("Volume", "HOLD", 0.0, "Volume data is unavailable.")

    lookback = min(VOLUME_LOOKBACK, len(df) - 1)
    latest_volume = float(df["Volume"].iloc[-1])
    average_volume = float(df["Volume"].iloc[-lookback - 1 : -1].mean())

    if average_volume <= 0:
        return ModelVote("Volume", "HOLD", 0.0, "Average volume is unavailable.")

    ratio = latest_volume / average_volume

    if ratio >= 1.25:
        return ModelVote("Volume", "BUY", min((ratio - 1.0) / 1.5, 1.0), f"Volume is {ratio:.2f}x average.")

    if ratio < MIN_VOLUME_RATIO:
        return ModelVote("Volume", "HOLD", -0.25, f"Volume is weak at {ratio:.2f}x average.")

    return ModelVote("Volume", "HOLD", 0.15, f"Volume is acceptable at {ratio:.2f}x average.")


def analyze_volatility_model(df):
    lookback = min(VOLATILITY_LOOKBACK, len(df))
    recent = df.tail(lookback)

    if recent.empty:
        return ModelVote("Volatility", "HOLD", 0.0, "Volatility data is unavailable.")

    price = float(recent["Close"].iloc[-1])
    high = float(recent["High"].max())
    low = float(recent["Low"].min())

    if price <= 0:
        return ModelVote("Volatility", "HOLD", 0.0, "Price is unavailable.")

    volatility_pct = ((high - low) / price) * 100

    if volatility_pct < MIN_SCALP_VOLATILITY_PCT:
        return ModelVote("Volatility", "HOLD", -0.35, f"Range is too quiet at {volatility_pct:.3f}%.")

    if volatility_pct > MAX_SCALP_VOLATILITY_PCT:
        return ModelVote("Volatility", "HOLD", -0.55, f"Range is too wild at {volatility_pct:.3f}%.")

    return ModelVote("Volatility", "BUY", 0.35, f"Range is tradable at {volatility_pct:.3f}%.")


def analyze_price_action_model(df):
    if len(df) < 4:
        return ModelVote("Price Action", "HOLD", 0.0, "Not enough candles for price action.")

    latest = df.iloc[-1]
    previous_close = float(df["Close"].iloc[-2])
    close = float(latest["Close"])
    open_price = float(latest["Open"])
    high = float(latest["High"])
    low = float(latest["Low"])
    candle_range = high - low

    if previous_close <= 0 or candle_range <= 0:
        return ModelVote("Price Action", "HOLD", 0.0, "Candle structure is unavailable.")

    body_position = (close - low) / candle_range
    move_pct = ((close - previous_close) / previous_close) * 100

    if close > open_price and body_position >= 0.65:
        return ModelVote("Price Action", "BUY", min(abs(move_pct) / 0.4 + 0.2, 1.0), "Latest candle closed strong.")

    if close < open_price and body_position <= 0.35:
        return ModelVote("Price Action", "SELL", -min(abs(move_pct) / 0.4 + 0.2, 1.0), "Latest candle closed weak.")

    return ModelVote("Price Action", "HOLD", 0.0, "Latest candle is indecisive.")


def analyze_weekly_trend_model(weekly_context):
    if not weekly_context or not weekly_context.get("data_available"):
        return ModelVote("Weekly Trend", "HOLD", 0.0, "Weekly data is unavailable.")

    week_change_pct = weekly_context["week_change_pct"]
    score = max(min(week_change_pct / 5.0, 1.0), -1.0)

    if score > 0.15:
        return ModelVote("Weekly Trend", "BUY", score, f"Price is up {week_change_pct:.2f}% over the last 7 days.")

    if score < -0.15:
        return ModelVote("Weekly Trend", "SELL", score, f"Price is down {abs(week_change_pct):.2f}% over the last 7 days.")

    return ModelVote("Weekly Trend", "HOLD", score, f"Weekly trend is flat ({week_change_pct:+.2f}%).")


def run_market_models(df):
    return [
        analyze_rsi_model(df),
        analyze_ema_trend_model(df),
        analyze_volume_model(df),
        analyze_volatility_model(df),
        analyze_price_action_model(df),
    ]
