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


def get_historical_market_data(symbol, timeframe, since_ms, until_ms=None, limit_per_call=1000):
    all_candles = []
    next_since = since_ms
    until_ms = until_ms or exchange.milliseconds()

    while next_since < until_ms:
        candles = exchange.fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            since=next_since,
            limit=limit_per_call,
        )

        if not candles:
            break

        for candle in candles:
            if candle[0] <= until_ms:
                all_candles.append(candle)

        last_timestamp = candles[-1][0]
        next_since = last_timestamp + 1

        if len(candles) < limit_per_call:
            break

    df = pd.DataFrame(
        all_candles,
        columns=[
            "Timestamp",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ],
    )

    if df.empty:
        return df

    df = df.drop_duplicates(subset=["Timestamp"])
    df = df.sort_values("Timestamp")
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="ms")
    df = df.reset_index(drop=True)

    return df


def get_last_24h_1s_market_data(symbol):
    now_ms = exchange.milliseconds()
    since_ms = now_ms - (24 * 60 * 60 * 1000)

    return get_historical_market_data(
        symbol=symbol,
        timeframe="1s",
        since_ms=since_ms,
        until_ms=now_ms,
    )


def get_last_week_market_data(symbol, timeframe="1h", lookback_days=7):
    now_ms = exchange.milliseconds()
    since_ms = now_ms - (lookback_days * 24 * 60 * 60 * 1000)

    return get_historical_market_data(
        symbol=symbol,
        timeframe=timeframe,
        since_ms=since_ms,
        until_ms=now_ms,
    )


def get_regime_market_data(symbol, timeframe="1h", lookback_days=30):
    now_ms = exchange.milliseconds()
    since_ms = now_ms - (lookback_days * 24 * 60 * 60 * 1000)

    return get_historical_market_data(
        symbol=symbol,
        timeframe=timeframe,
        since_ms=since_ms,
        until_ms=now_ms,
    )


def get_last_year_market_data(symbol, timeframe="1h", lookback_days=365):
    now_ms = exchange.milliseconds()
    since_ms = now_ms - (lookback_days * 24 * 60 * 60 * 1000)

    return get_historical_market_data(
        symbol=symbol,
        timeframe=timeframe,
        since_ms=since_ms,
        until_ms=now_ms,
    )
