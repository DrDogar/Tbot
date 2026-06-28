import ccxt

exchange = ccxt.binance()

def get_bitcoin_price():
    ticker = exchange.fetch_ticker("BTC/USDT")
    return ticker["last"]