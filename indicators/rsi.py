from ta.momentum import RSIIndicator


def calculate_rsi(df):

    rsi = RSIIndicator(close=df["Close"], window=14)

    df["RSI"] = rsi.rsi()

    return df