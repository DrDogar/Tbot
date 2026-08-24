from dataclasses import dataclass
from typing import Callable, Optional

from bots.entry_strategies import (
    aggressive_voter_entry,
    breakout_entry,
    momentum_rider_entry,
    scalper_entry,
    trend_follower_entry,
)


@dataclass(frozen=True)
class BotConfig:
    key: str
    name: str
    description: str
    entry_fn: Optional[Callable]
    stop_loss_pct: float
    take_profit_pct: Optional[float]
    trailing_stop_pct: Optional[float]
    starting_quote_balance: float
    uses_neural_net: bool = False
    uses_forest: bool = False
    uses_ensemble: bool = False


BOTS = [
    BotConfig(
        key="momentum_rider",
        name="Momentum Rider",
        description="Rides confirmed uptrends with a trailing stop on winners. Gives losers room (10% stop) instead of cutting fast.",
        entry_fn=momentum_rider_entry,
        stop_loss_pct=10.0,
        take_profit_pct=None,
        trailing_stop_pct=0.4,
        starting_quote_balance=1000.0,
    ),
    BotConfig(
        key="scalper",
        name="Scalper",
        description="Fast, small trades off short-term RSI dips. Tiny take-profit, high frequency, wide (10%) stop-loss.",
        entry_fn=scalper_entry,
        stop_loss_pct=10.0,
        take_profit_pct=0.35,
        trailing_stop_pct=None,
        starting_quote_balance=1000.0,
    ),
    BotConfig(
        key="breakout_hunter",
        name="Breakout Hunter",
        description="Jumps on volume-backed breakouts above recent highs, with a fixed target and stop.",
        entry_fn=breakout_entry,
        stop_loss_pct=10.0,
        take_profit_pct=1.0,
        trailing_stop_pct=None,
        starting_quote_balance=1000.0,
    ),
    BotConfig(
        key="trend_follower",
        name="Weekly Trend Follower",
        description="Only trades with the 7-day trend, entering on short-term pullbacks. Wider stop, wider target.",
        entry_fn=trend_follower_entry,
        stop_loss_pct=10.0,
        take_profit_pct=1.6,
        trailing_stop_pct=None,
        starting_quote_balance=1000.0,
    ),
    BotConfig(
        key="aggressive_voter",
        name="Aggressive Multi-Vote",
        description="The full RSI/EMA/volume/volatility/price-action/weekly-trend model, with a low confidence bar.",
        entry_fn=aggressive_voter_entry,
        stop_loss_pct=10.0,
        take_profit_pct=0.8,
        trailing_stop_pct=None,
        starting_quote_balance=1000.0,
    ),
    BotConfig(
        key="neural_net",
        name="Neural Net Trader",
        description=(
            "A small neural network (built from scratch, trained locally, no API/cost) fitted on each coin's "
            "last full year of data. Predicts BUY/HOLD/SELL from the same signals the other bots use."
        ),
        entry_fn=None,
        stop_loss_pct=10.0,
        take_profit_pct=0.8,
        trailing_stop_pct=None,
        starting_quote_balance=1000.0,
        uses_neural_net=True,
    ),
    BotConfig(
        key="random_forest",
        name="Random Forest Trader",
        description=(
            "A from-scratch random forest (25 bagged, feature-sampled decision trees, trained locally, "
            "no API/cost) fitted on each coin's last full year of data. A different kind of AI than the "
            "neural net -- votes BUY/HOLD/SELL by majority across trees instead of gradient descent."
        ),
        entry_fn=None,
        stop_loss_pct=10.0,
        take_profit_pct=0.8,
        trailing_stop_pct=None,
        starting_quote_balance=1000.0,
        uses_forest=True,
    ),
    BotConfig(
        key="ensemble_meta",
        name="Ensemble Meta-Trader",
        description=(
            "The smartest bot in the arena: a stacking ensemble trained not just on raw price signals, but on "
            "what the Neural Net Trader and Random Forest Trader already predicted at each point in the last "
            "year -- learning when to trust which one instead of guessing from scratch. Built from scratch, "
            "trained locally, no API/cost."
        ),
        entry_fn=None,
        stop_loss_pct=10.0,
        take_profit_pct=0.8,
        trailing_stop_pct=None,
        starting_quote_balance=1000.0,
        uses_ensemble=True,
    ),
]

BOTS_BY_KEY = {bot.key: bot for bot in BOTS}
