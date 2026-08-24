from config.settings import CURRENT_SYMBOL, DEFAULT_LIMIT, DEFAULT_TIMEFRAME
from data.collector import get_market_data
from indicators.rsi import calculate_rsi
from risk.spot_guard import build_spot_trade_plan
from strategies.rsi_scalper import generate_rsi_scalping_signal


def show_dashboard():

    df = get_market_data(
        symbol=CURRENT_SYMBOL,
        timeframe=DEFAULT_TIMEFRAME,
        limit=DEFAULT_LIMIT,
    )

    df = calculate_rsi(df)

    signal = generate_rsi_scalping_signal(df)
    plan = build_spot_trade_plan(signal, CURRENT_SYMBOL)

    print("\n")
    print("=" * 50)
    print("          TBOT MARKET DASHBOARD")
    print("=" * 50)

    print(f"Symbol          : {CURRENT_SYMBOL}")
    print(f"Current Price   : ${signal.price:,.2f}")
    print(f"Current RSI     : {signal.rsi:.2f}")
    print(f"Market Mood     : {signal.mood_score:.2f}")
    print(f"Scalp Possible  : {'YES' if signal.scalp_possible else 'NO'}")
    print(f"Signal          : {signal.action}")
    print(f"Confidence      : {signal.confidence:.0%}")
    print(f"Reason          : {signal.reason}")
    print(f"Trade Mode      : {plan.mode.upper()}")
    print(f"Risk Decision   : {'ALLOWED' if plan.allowed else 'BLOCKED'}")
    print(f"Risk Reason     : {plan.reason}")
    print(f"Fee (est.)      : ${plan.fee_quote:,.4f}")

    print("=" * 50)
