import json

import numpy as np

from config.settings import DEFAULT_LIMIT, WEEKLY_LOOKBACK_DAYS
from indicators.rsi import calculate_rsi
from strategies.market_models import (
    analyze_ema_trend_model,
    analyze_price_action_model,
    analyze_rsi_model,
    analyze_volatility_model,
    analyze_volume_model,
)
from strategies.weekly_context import summarize_weekly_context

FEATURE_NAMES = ["rsi", "ema_trend", "volume", "volatility", "price_action", "weekly_trend"]
ACTIONS = ["SELL", "HOLD", "BUY"]

HIDDEN_UNITS = 6
EPOCHS = 400
LEARNING_RATE = 0.08
LOOKAHEAD = 3
MOVE_THRESHOLD_PCT = 0.12
MIN_TRAINING_SAMPLES = 40

# Bounded windows, not the whole growing history, so training sees the same
# amount of context per sample as live inference does (get_market_data(limit=DEFAULT_LIMIT))
# instead of an ever-larger window that would both mismatch live inference and make
# building a year of training data quadratically slow.
SIGNAL_WINDOW = DEFAULT_LIMIT
WEEKLY_WINDOW = WEEKLY_LOOKBACK_DAYS * 24


def feature_vector(df, weekly_context):
    weekly_score = 0.0

    if weekly_context and weekly_context.get("data_available"):
        weekly_score = max(min(weekly_context["week_change_pct"] / 5.0, 1.0), -1.0)

    return np.array(
        [
            analyze_rsi_model(df).score,
            analyze_ema_trend_model(df).score,
            analyze_volume_model(df).score,
            analyze_volatility_model(df).score,
            analyze_price_action_model(df).score,
            weekly_score,
        ],
        dtype=float,
    )


def build_training_dataset(history_df, lookahead=LOOKAHEAD, threshold_pct=MOVE_THRESHOLD_PCT):
    min_rows = SIGNAL_WINDOW + lookahead + MIN_TRAINING_SAMPLES

    if history_df.empty or len(history_df) < min_rows:
        return np.empty((0, len(FEATURE_NAMES))), np.empty((0,), dtype=int)

    df = calculate_rsi(history_df.copy()).dropna().reset_index(drop=True)
    features = []
    labels = []

    for i in range(SIGNAL_WINDOW, len(df) - lookahead):
        # Bounded windows ending at i, matching what live inference actually sees
        # (the last SIGNAL_WINDOW candles, plus a trailing WEEKLY_WINDOW for the weekly-trend feature).
        signal_window = df.iloc[i - SIGNAL_WINDOW + 1 : i + 1]
        weekly_window = df.iloc[max(0, i - WEEKLY_WINDOW + 1) : i + 1]
        trailing_context = summarize_weekly_context(weekly_window)

        current_price = float(df.iloc[i]["Close"])
        future_price = float(df.iloc[i + lookahead]["Close"])
        change_pct = ((future_price - current_price) / current_price) * 100 if current_price else 0.0

        if change_pct > threshold_pct:
            label = 2
        elif change_pct < -threshold_pct:
            label = 0
        else:
            label = 1

        features.append(feature_vector(signal_window, trailing_context))
        labels.append(label)

    return np.array(features), np.array(labels, dtype=int)


def _init_weights(input_dim, hidden_dim, output_dim, seed):
    rng = np.random.default_rng(seed)
    return {
        "W1": rng.normal(0, 0.5, size=(input_dim, hidden_dim)),
        "b1": np.zeros(hidden_dim),
        "W2": rng.normal(0, 0.5, size=(hidden_dim, output_dim)),
        "b2": np.zeros(output_dim),
    }


def train_network(features, labels, hidden_dim=HIDDEN_UNITS, epochs=EPOCHS, lr=LEARNING_RATE, seed=7):
    n, input_dim = features.shape
    weights = _init_weights(input_dim, hidden_dim, len(ACTIONS), seed)

    y_onehot = np.zeros((n, len(ACTIONS)))
    y_onehot[np.arange(n), labels] = 1

    for _ in range(epochs):
        h_linear = features @ weights["W1"] + weights["b1"]
        h = np.maximum(0, h_linear)
        logits = h @ weights["W2"] + weights["b2"]
        logits -= logits.max(axis=1, keepdims=True)
        exp_logits = np.exp(logits)
        probs = exp_logits / exp_logits.sum(axis=1, keepdims=True)

        grad_logits = (probs - y_onehot) / n
        grad_W2 = h.T @ grad_logits
        grad_b2 = grad_logits.sum(axis=0)

        grad_h = grad_logits @ weights["W2"].T
        grad_h[h_linear <= 0] = 0
        grad_W1 = features.T @ grad_h
        grad_b1 = grad_h.sum(axis=0)

        weights["W1"] -= lr * grad_W1
        weights["b1"] -= lr * grad_b1
        weights["W2"] -= lr * grad_W2
        weights["b2"] -= lr * grad_b2

    return weights


def predict_proba(weights, features):
    h = np.maximum(0, features @ weights["W1"] + weights["b1"])
    logits = h @ weights["W2"] + weights["b2"]
    logits -= logits.max()
    exp_logits = np.exp(logits)
    return exp_logits / exp_logits.sum()


def predict(weights, features):
    probs = predict_proba(weights, features)
    predicted_index = int(np.argmax(probs))
    return ACTIONS[predicted_index], float(probs[predicted_index])


def train_symbol_model(week_df):
    features, labels = build_training_dataset(week_df)

    if len(features) < MIN_TRAINING_SAMPLES:
        return None

    return train_network(features, labels)


def weights_to_json(weights):
    return {key: value.tolist() for key, value in weights.items()}


def weights_from_json(payload):
    return {key: np.array(value, dtype=float) for key, value in payload.items()}


def save_all_weights(weights_by_symbol, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {symbol: weights_to_json(weights) for symbol, weights in weights_by_symbol.items() if weights}

    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file)


def load_all_weights(path):
    if not path.exists():
        return {}

    with open(path, "r", encoding="utf-8") as file:
        payload = json.load(file)

    return {symbol: weights_from_json(data) for symbol, data in payload.items()}
