from config.settings import CURRENT_SYMBOL
from dashboard.market_dashboard import show_dashboard
from exchange.binance import get_live_price
from data.collector import get_market_data
from charts.plotter import draw_chart
from indicators.rsi import calculate_rsi
from services.market_service import get_current_market

def dashboard():

    show_dashboard()

def live_price():

    print("\n====================================")
    print("      LIVE BTC PRICE")
    print("====================================")

    price = get_live_price(CURRENT_SYMBOL)

    print(f"\nCurrent {CURRENT_SYMBOL} Price : ${price:,.2f}")


def download_market_data():


    df = get_current_market()

    df.to_csv("btc_data.csv", index=False)

    print("\nMarket data downloaded successfully!")

    print("Saved as btc_data.csv")


def show_chart():

    df = get_current_market()

    draw_chart(df, CURRENT_SYMBOL)


def rsi_analysis():

    df = get_current_market()

    df = calculate_rsi(df)

    latest = df.iloc[-1]

    print("\n====================================")
    print("        RSI ANALYSIS")
    print("====================================")

    print(f"Price : ${latest['Close']:,.2f}")
    print(f"RSI   : {latest['RSI']:.2f}")

    if latest["RSI"] > 70:

        print("\nStatus : OVERBOUGHT")
        print("Suggestion : Consider waiting for a pullback.")

    elif latest["RSI"] < 30:

        print("\nStatus : OVERSOLD")
        print("Suggestion : Watch for a possible buying opportunity.")

    else:

        print("\nStatus : NEUTRAL")
        print("Suggestion : Wait for confirmation.")