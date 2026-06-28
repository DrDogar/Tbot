import ccxt

exchange = ccxt.binance()


def get_live_price(symbol):

    ticker = exchange.fetch_ticker(symbol)

    return ticker["last"]