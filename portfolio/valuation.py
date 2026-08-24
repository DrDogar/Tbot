from exchange.binance import get_live_price


def compute_portfolio_summary(portfolio):
    market_value = 0.0
    prices = {}

    for symbol, position in portfolio.positions.items():
        if position.base_amount <= 0:
            continue

        try:
            price = get_live_price(symbol)
        except Exception:
            price = position.average_entry_price

        prices[symbol] = price
        market_value += position.base_amount * price

    equity = portfolio.quote_balance + market_value
    pnl = equity - portfolio.starting_quote_balance
    pnl_pct = (pnl / portfolio.starting_quote_balance * 100) if portfolio.starting_quote_balance else 0.0

    return {
        "market_value": market_value,
        "equity": equity,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "prices": prices,
    }
