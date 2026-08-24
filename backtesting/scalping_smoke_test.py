from dataclasses import dataclass

import pandas as pd

from config.settings import (
    BACKTEST_MODEL_WINDOW,
    BACKTEST_SIGNAL_STEP_SECONDS,
    SCALP_LOOKAHEAD_SECONDS,
    SCALP_MAX_ADVERSE_PCT,
    SCALP_TARGET_PCT,
)
from indicators.rsi import calculate_rsi
from strategies.rsi_scalper import generate_scalping_signal


@dataclass(frozen=True)
class SmokeTestResult:
    total_rows: int
    evaluated_points: int
    opportunities: int
    captured: int
    missed: int
    false_signals: int
    capture_rate: float
    model_signal_rate: float
    events: pd.DataFrame


def run_scalping_smoke_test(df):
    prepared = calculate_rsi(df.copy())
    prepared = prepared.dropna().reset_index(drop=True)

    events = []
    start_index = max(BACKTEST_MODEL_WINDOW, 2)
    end_index = len(prepared) - SCALP_LOOKAHEAD_SECONDS - 1

    if end_index <= start_index:
        return _empty_result(len(df))

    evaluated_points = 0
    model_signal_count = 0

    for index in range(start_index, end_index, BACKTEST_SIGNAL_STEP_SECONDS):
        window = prepared.iloc[index - BACKTEST_MODEL_WINDOW + 1 : index + 1]
        current = prepared.iloc[index]
        future = prepared.iloc[index + 1 : index + SCALP_LOOKAHEAD_SECONDS + 1]

        signal = generate_scalping_signal(window)
        opportunity = _detect_opportunity(float(current["Close"]), future)

        model_action = signal.action if signal.scalp_possible else "HOLD"
        captured = opportunity in ("BUY", "SELL") and model_action == opportunity
        missed = opportunity in ("BUY", "SELL") and model_action != opportunity
        false_signal = model_action in ("BUY", "SELL") and opportunity == "NONE"

        evaluated_points += 1
        if model_action in ("BUY", "SELL"):
            model_signal_count += 1

        if captured or missed or false_signal:
            events.append(
                {
                    "Timestamp": current["Timestamp"],
                    "Price": float(current["Close"]),
                    "Opportunity": opportunity,
                    "ModelAction": model_action,
                    "Captured": captured,
                    "Missed": missed,
                    "FalseSignal": false_signal,
                    "MoodScore": signal.mood_score,
                    "Confidence": signal.confidence,
                    "Reason": signal.reason,
                }
            )

    events_df = pd.DataFrame(events)
    opportunities = int((events_df["Opportunity"] != "NONE").sum()) if not events_df.empty else 0
    captured = int(events_df["Captured"].sum()) if not events_df.empty else 0
    missed = int(events_df["Missed"].sum()) if not events_df.empty else 0
    false_signals = int(events_df["FalseSignal"].sum()) if not events_df.empty else 0

    capture_rate = captured / opportunities if opportunities else 0.0
    model_signal_rate = model_signal_count / evaluated_points if evaluated_points else 0.0

    return SmokeTestResult(
        total_rows=len(prepared),
        evaluated_points=evaluated_points,
        opportunities=opportunities,
        captured=captured,
        missed=missed,
        false_signals=false_signals,
        capture_rate=capture_rate,
        model_signal_rate=model_signal_rate,
        events=events_df,
    )


def _detect_opportunity(price, future):
    future_high = float(future["High"].max())
    future_low = float(future["Low"].min())

    up_pct = ((future_high - price) / price) * 100
    down_pct = ((price - future_low) / price) * 100

    buy_available = up_pct >= SCALP_TARGET_PCT and down_pct <= SCALP_MAX_ADVERSE_PCT
    sell_available = down_pct >= SCALP_TARGET_PCT and up_pct <= SCALP_MAX_ADVERSE_PCT

    if buy_available and not sell_available:
        return "BUY"

    if sell_available and not buy_available:
        return "SELL"

    if buy_available and sell_available:
        return "BUY" if up_pct >= down_pct else "SELL"

    return "NONE"


def _empty_result(total_rows):
    return SmokeTestResult(
        total_rows=total_rows,
        evaluated_points=0,
        opportunities=0,
        captured=0,
        missed=0,
        false_signals=0,
        capture_rate=0.0,
        model_signal_rate=0.0,
        events=pd.DataFrame(),
    )
