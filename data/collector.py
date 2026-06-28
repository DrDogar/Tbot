import pandas as pd

from exchange.binance import exchange


def get_market_data(symbol, timeframe="1m", limit=100):

    candles = exchange.fetch_ohlcv(
        symbol=symbol,
        timeframe=timeframe,
        limit=limit,
    )

    df = pd.DataFrame(
        candles,
        columns=[
            "Timestamp",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ],
    )

    df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="ms")

    return df