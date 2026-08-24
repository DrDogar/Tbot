import numpy as np

from bots.forest_model import predict_proba as forest_predict_proba
from bots.neural_model import (
    FEATURE_NAMES,
    LOOKAHEAD,
    MIN_TRAINING_SAMPLES,
    MOVE_THRESHOLD_PCT,
    SIGNAL_WINDOW,
    WEEKLY_WINDOW,
    feature_vector,
)
from bots.neural_model import predict_proba as neural_predict_proba
from indicators.rsi import calculate_rsi
from strategies.weekly_context import summarize_weekly_context

# A stacking ensemble: instead of learning from raw technical features alone, this
# model also sees what the Neural Net Trader and Random Forest Trader already predict
# at each bar, and learns when to trust which one -- i.e. it's trained on the other
# two bots' track record, not just on price data. It reuses neural_model's MLP
# trainer/predict/serialization as-is (same {W1,b1,W2,b2} shape), just with a richer
# input vector.
STACK_FEATURE_NAMES = FEATURE_NAMES + [
    "neural_sell",
    "neural_hold",
    "neural_buy",
    "forest_sell",
    "forest_hold",
    "forest_buy",
]


def stacked_feature_vector(df, weekly_context, neural_weights, forest):
    base_features = feature_vector(df, weekly_context)
    neural_probs = neural_predict_proba(neural_weights, base_features)
    forest_probs = forest_predict_proba(forest, base_features)
    return np.concatenate([base_features, neural_probs, forest_probs])


def build_stacked_dataset(history_df, neural_weights, forest, lookahead=LOOKAHEAD, threshold_pct=MOVE_THRESHOLD_PCT):
    min_rows = SIGNAL_WINDOW + lookahead + MIN_TRAINING_SAMPLES

    if history_df.empty or len(history_df) < min_rows or neural_weights is None or forest is None:
        return np.empty((0, len(STACK_FEATURE_NAMES))), np.empty((0,), dtype=int)

    df = calculate_rsi(history_df.copy()).dropna().reset_index(drop=True)
    features = []
    labels = []

    for i in range(SIGNAL_WINDOW, len(df) - lookahead):
        signal_window = df.iloc[i - SIGNAL_WINDOW + 1 : i + 1]
        weekly_window = df.iloc[max(0, i - WEEKLY_WINDOW + 1) : i + 1]
        trailing_context = summarize_weekly_context(weekly_window)

        stacked = stacked_feature_vector(signal_window, trailing_context, neural_weights, forest)

        current_price = float(df.iloc[i]["Close"])
        future_price = float(df.iloc[i + lookahead]["Close"])
        change_pct = ((future_price - current_price) / current_price) * 100 if current_price else 0.0

        if change_pct > threshold_pct:
            label = 2
        elif change_pct < -threshold_pct:
            label = 0
        else:
            label = 1

        features.append(stacked)
        labels.append(label)

    return np.array(features), np.array(labels, dtype=int)
