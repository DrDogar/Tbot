from config.settings import (
    CURRENT_SYMBOL,
    DEFAULT_TIMEFRAME,
    DEFAULT_LIMIT,
)

from data.collector import get_market_data


def get_current_market():

    return get_market_data(
        symbol=CURRENT_SYMBOL,
        timeframe=DEFAULT_TIMEFRAME,
        limit=DEFAULT_LIMIT,
    )