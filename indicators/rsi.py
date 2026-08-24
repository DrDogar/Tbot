from ta.momentum import RSIIndicator

from config.settings import RSI_PERIOD


def calculate_rsi(df):

    rsi = RSIIndicator(close=df["Close"], window=RSI_PERIOD)

    df["RSI"] = rsi.rsi()

    return df
