import ccxt

exchange = ccxt.binance(
    {
        "enableRateLimit": True,
        "options": {
            "defaultType": "spot",
        },
    }
)


def get_live_price(symbol):

    ticker = exchange.fetch_ticker(symbol)

    return ticker["last"]
