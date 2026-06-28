from data.collector import get_market_data
from indicators.rsi import calculate_rsi


def show_dashboard():

    df = get_market_data(
        symbol="BTC/USDT",
        timeframe="5m",
        limit=100,
    )

    df = calculate_rsi(df)

    latest = df.iloc[-1]

    print("\n")
    print("=" * 50)
    print("🤖          TBOT MARKET DASHBOARD")
    print("=" * 50)

    print(f"Symbol          : BTC/USDT")
    print(f"Current Price   : ${latest['Close']:,.2f}")
    print(f"Current RSI     : {latest['RSI']:.2f}")

    if latest["RSI"] > 70:
        signal = "SELL"
        status = "OVERBOUGHT"

    elif latest["RSI"] < 30:
        signal = "BUY"
        status = "OVERSOLD"

    else:
        signal = "WAIT"
        status = "NEUTRAL"

    print(f"Market Status   : {status}")
    print(f"Recommendation  : {signal}")

    print("=" * 50)