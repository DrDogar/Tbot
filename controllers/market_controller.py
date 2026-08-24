from config.settings import CURRENT_SYMBOL
from backtesting.scalping_smoke_test import run_scalping_smoke_test
from dashboard.market_dashboard import show_dashboard
from exchange.binance import get_live_price
from data.collector import get_last_24h_1s_market_data, get_market_data
from charts.plotter import draw_chart
from indicators.rsi import calculate_rsi
from risk.spot_guard import build_spot_trade_plan
from services.market_service import get_current_market
from strategies.rsi_scalper import generate_rsi_scalping_signal


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
    signal = generate_rsi_scalping_signal(df)

    print("\n====================================")
    print("        RSI ANALYSIS")
    print("====================================")

    print(f"Price : ${latest['Close']:,.2f}")
    print(f"RSI   : {latest['RSI']:.2f}")

    if signal.action == "SELL":

        print("\nStatus : OVERBOUGHT")
        print("Suggestion : Consider waiting for a pullback or protecting spot holdings.")

    elif signal.action == "BUY":

        print("\nStatus : OVERSOLD")
        print("Suggestion : Watch for a possible buying opportunity.")

    else:

        print("\nStatus : NEUTRAL")
        print("Suggestion : Wait for confirmation.")


def trade_preview():

    df = get_current_market()

    df = calculate_rsi(df)

    signal = generate_rsi_scalping_signal(df)
    plan = build_spot_trade_plan(signal, CURRENT_SYMBOL)

    print("\n====================================")
    print("        PAPER TRADE PREVIEW")
    print("====================================")

    print(f"Symbol       : {plan.symbol}")
    print(f"Mode         : {plan.mode.upper()}")
    print(f"Mood Score   : {signal.mood_score:.2f}")
    print(f"Scalp Ready  : {'YES' if signal.scalp_possible else 'NO'}")
    print(f"Signal       : {signal.action}")
    print(f"Confidence   : {signal.confidence:.0%}")
    print(f"Price        : ${plan.price:,.2f}")
    print(f"Decision     : {'ALLOWED' if plan.allowed else 'BLOCKED'}")
    print(f"Reason       : {plan.reason}")

    if plan.allowed:
        print(f"Side         : {plan.side}")
        print(f"Quote Amount : ${plan.quote_amount:,.2f}")
        print(f"Base Amount  : {plan.base_amount:.8f}")
        print(f"Fee (est.)   : ${plan.fee_quote:,.4f}")

    print("\nNo real order was sent.")


def market_model_analysis():

    df = get_current_market()

    df = calculate_rsi(df)

    signal = generate_rsi_scalping_signal(df)

    print("\n====================================")
    print("        MARKET MODEL ANALYSIS")
    print("====================================")

    print(f"Symbol       : {CURRENT_SYMBOL}")
    print(f"Price        : ${signal.price:,.2f}")
    print(f"Mood Score   : {signal.mood_score:.2f}")
    print(f"Scalp Ready  : {'YES' if signal.scalp_possible else 'NO'}")
    print(f"Final Signal : {signal.action}")
    print(f"Confidence   : {signal.confidence:.0%}")
    print(f"Reason       : {signal.reason}")

    print("\nModels:")
    for vote in signal.votes:
        print(f"- {vote.name}: {vote.bias} | score {vote.score:.2f} | {vote.detail}")


def last_24h_scalping_smoke_test():

    print("\n====================================")
    print("   24H 1S SCALPING SMOKE TEST")
    print("====================================")
    print(f"Fetching last 24h of 1-second candles for {CURRENT_SYMBOL}...")

    df = get_last_24h_1s_market_data(CURRENT_SYMBOL)

    if df.empty:
        print("\nNo data returned from Binance.")
        return

    data_path = "binance_1s_24h.csv"
    events_path = "scalping_smoke_test_events.csv"
    df.to_csv(data_path, index=False)

    print(f"Fetched rows  : {len(df):,}")
    print(f"First candle  : {df.iloc[0]['Timestamp']}")
    print(f"Last candle   : {df.iloc[-1]['Timestamp']}")
    print(f"Saved data    : {data_path}")
    print("\nRunning model smoke test...")

    result = run_scalping_smoke_test(df)
    result.events.to_csv(events_path, index=False)

    print("\nResults")
    print("-" * 40)
    print(f"Evaluated Points : {result.evaluated_points:,}")
    print(f"Opportunities    : {result.opportunities:,}")
    print(f"Captured          : {result.captured:,}")
    print(f"Missed            : {result.missed:,}")
    print(f"False Signals     : {result.false_signals:,}")
    print(f"Capture Rate      : {result.capture_rate:.1%}")
    print(f"Model Signal Rate : {result.model_signal_rate:.1%}")
    print(f"Saved Events      : {events_path}")

    if not result.events.empty:
        print("\nSample Events")
        print("-" * 40)
        for _, event in result.events.head(10).iterrows():
            print(
                f"{event['Timestamp']} | opportunity={event['Opportunity']} | "
                f"model={event['ModelAction']} | captured={event['Captured']} | "
                f"confidence={event['Confidence']:.0%}"
            )
