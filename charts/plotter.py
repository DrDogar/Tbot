import mplfinance as mpf

from config.settings import CHART_STYLE


def draw_chart(df, symbol):

    df = df.copy()

    df.set_index("Timestamp", inplace=True)

    mpf.plot(
        df,
        type="candle",
        style=CHART_STYLE,
        title=symbol,
        ylabel="Price",
        volume=True,
    )