from dataclasses import dataclass
from typing import Callable, Optional

from bots.entry_strategies import (
    breakout_entry,
    momentum_rider_entry,
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
    uses_trend_ai: bool = False


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
            "A stacking ensemble trained not just on raw price signals, but on what the Neural Net Trader and "
            "Random Forest Trader already predicted at each point in the last year -- learning when to trust "
            "which one instead of guessing from scratch. Built from scratch, trained locally, no API/cost."
        ),
        entry_fn=None,
        stop_loss_pct=10.0,
        take_profit_pct=0.8,
        trailing_stop_pct=None,
        starting_quote_balance=1000.0,
        uses_ensemble=True,
    ),
    BotConfig(
        key="trend_ai",
        name="Patient Trend AI",
        description=(
            "The most patient bot in the arena: a from-scratch neural net trained to spot 2-day-ahead moves "
            "(not 3-hour ones), using an extra 30-day macro regime feature the other bots don't see. It only "
            "acts on genuinely large, sustained trends -- otherwise it sits in cash. No take-profit cap, so a "
            "real trend is allowed to run, and a wide 3% trailing stop instead of a tight one. Built to wait "
            "out down/choppy seasons and ride real up-seasons. Trained locally, no API/cost."
        ),
        entry_fn=None,
        stop_loss_pct=10.0,
        take_profit_pct=None,
        trailing_stop_pct=3.0,
        starting_quote_balance=1000.0,
        uses_trend_ai=True,
    ),
]

BOTS_BY_KEY = {bot.key: bot for bot in BOTS}
