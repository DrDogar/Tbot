from dataclasses import dataclass

from config.settings import WEEKLY_LOOKBACK_DAYS
from indicators.rsi import calculate_rsi
from strategies.weekly_context import summarize_weekly_context

# Bounded lookback per bar so training on a full year of hourly candles stays O(n)
# instead of re-slicing the whole history on every bar (which is fine for a week of
# data but grinds to a halt over a year). ~8 days of local context is plenty for the
# EMA(50)/RSI/breakout indicators these bots use.
SIGNAL_WINDOW = 200
WEEKLY_WINDOW = WEEKLY_LOOKBACK_DAYS * 24


@dataclass(frozen=True)
class TrainingResult:
    symbol: str
    trades: int
    win_rate: float
    total_return_pct: float


def train_bot_on_symbol(bot, symbol, history_df):
    min_rows = SIGNAL_WINDOW + 20

    if history_df.empty or len(history_df) < min_rows:
        return TrainingResult(symbol=symbol, trades=0, win_rate=0.0, total_return_pct=0.0)

    df = calculate_rsi(history_df.copy()).dropna().reset_index(drop=True)

    entry_price = None
    peak_price = None
    trade_returns = []

    for i in range(SIGNAL_WINDOW, len(df)):
        price = float(df.iloc[i]["Close"])

        if entry_price is not None:
            peak_price = max(peak_price, price)
            change_pct = ((price - entry_price) / entry_price) * 100

            exit_now = change_pct <= -bot.stop_loss_pct

            if not exit_now and bot.trailing_stop_pct and change_pct > 0:
                drawdown_pct = ((price - peak_price) / peak_price) * 100
                exit_now = drawdown_pct <= -bot.trailing_stop_pct

            if not exit_now and bot.take_profit_pct and change_pct >= bot.take_profit_pct:
                exit_now = True

            if exit_now:
                trade_returns.append(change_pct)
                entry_price = None
                peak_price = None

            continue

        signal_window = df.iloc[i - SIGNAL_WINDOW + 1 : i + 1]
        weekly_window = df.iloc[max(0, i - WEEKLY_WINDOW + 1) : i + 1]
        weekly_context = summarize_weekly_context(weekly_window)
        signal = bot.entry_fn(signal_window, weekly_context)

        if signal.should_enter:
            entry_price = price
            peak_price = price

    trades = len(trade_returns)
    win_rate = (sum(1 for r in trade_returns if r > 0) / trades) if trades else 0.0
    total_return_pct = sum(trade_returns)

    return TrainingResult(symbol=symbol, trades=trades, win_rate=win_rate, total_return_pct=total_return_pct)


def is_coin_allowed_for_bot(training, bot_key, symbol):
    result = training.get(bot_key, {}).get(symbol)

    if not result or result["trades"] == 0:
        return True

    return result["total_return_pct"] > 0
