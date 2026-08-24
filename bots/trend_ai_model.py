import numpy as np

from bots.neural_model import FEATURE_NAMES, SIGNAL_WINDOW, feature_vector
from config.settings import REGIME_LOOKBACK_DAYS
from indicators.rsi import calculate_rsi
from strategies.weekly_context import summarize_weekly_context

# Patient Trend AI: the same MLP architecture/trainer as neural_model (reused as-is --
# see train_network/predict/weights_to_json/load_all_weights imports in bots/runner.py
# and bots/engine.py), but trained to answer a different question: not "what happens in
# the next few hours" but "is this the start of a real, multi-day move". Two things make
# that a genuinely different model rather than the same one with new numbers:
#
#   1. An extra "regime" feature -- price change over the last REGIME_LOOKBACK_DAYS
#      (30, vs. the 7-day feature every other bot already sees) -- so it can tell a
#      broad bull regime from a broad bear one, not just short-term wiggle.
#   2. A much longer label lookahead (3 days, not 3 hours) and a much higher move
#      threshold (2.5%, not 0.12%), so most bars simply aren't confident BUY/SELL
#      setups. That's deliberate: it should default to HOLD (stay in cash) through
#      chop and down-drift, and only fire on the kind of move worth holding through.
TREND_FEATURE_NAMES = FEATURE_NAMES + ["regime_trend"]

# A 3-day/2.5% target turned out to be too hard for this feature set -- the model just
# collapsed to always predicting HOLD (verified: training accuracy exactly matched the
# majority-class baseline). 2 days/1.5% is the longest, most selective target that still
# breaks that collapse and produces genuinely discriminating BUY/SELL/HOLD predictions,
# checked against real data across all 5 tracked coins. Still ~16x the lookahead and
# ~12x the move threshold of the other AI bots' 3-hour/0.12% target.
LONG_LOOKAHEAD = 24 * 2  # 2 days, in hourly bars
LONG_MOVE_THRESHOLD_PCT = 1.5
REGIME_WINDOW = REGIME_LOOKBACK_DAYS * 24

# A harder target needs more model capacity/training than the other AI bots' defaults
# (6 hidden units / 400 epochs) to actually learn instead of collapsing to the majority
# class -- also verified empirically.
HIDDEN_UNITS = 12
EPOCHS = 1200
LEARNING_RATE = 0.05


def regime_feature_vector(df, weekly_context, regime_context):
    base = feature_vector(df, weekly_context)
    regime_score = 0.0

    if regime_context and regime_context.get("data_available"):
        regime_score = max(min(regime_context["week_change_pct"] / 20.0, 1.0), -1.0)

    return np.concatenate([base, [regime_score]])


def build_long_training_dataset(history_df, lookahead=LONG_LOOKAHEAD, threshold_pct=LONG_MOVE_THRESHOLD_PCT):
    min_rows = REGIME_WINDOW + lookahead + 40

    if history_df.empty or len(history_df) < min_rows:
        return np.empty((0, len(TREND_FEATURE_NAMES))), np.empty((0,), dtype=int)

    df = calculate_rsi(history_df.copy()).dropna().reset_index(drop=True)
    features = []
    labels = []

    for i in range(REGIME_WINDOW, len(df) - lookahead):
        signal_window = df.iloc[max(0, i - SIGNAL_WINDOW + 1) : i + 1]
        weekly_window = df.iloc[max(0, i - (7 * 24) + 1) : i + 1]
        regime_window = df.iloc[i - REGIME_WINDOW + 1 : i + 1]

        weekly_context = summarize_weekly_context(weekly_window)
        regime_context = summarize_weekly_context(regime_window)

        current_price = float(df.iloc[i]["Close"])
        future_price = float(df.iloc[i + lookahead]["Close"])
        change_pct = ((future_price - current_price) / current_price) * 100 if current_price else 0.0

        if change_pct > threshold_pct:
            label = 2
        elif change_pct < -threshold_pct:
            label = 0
        else:
            label = 1

        features.append(regime_feature_vector(signal_window, weekly_context, regime_context))
        labels.append(label)

    return np.array(features), np.array(labels, dtype=int)
