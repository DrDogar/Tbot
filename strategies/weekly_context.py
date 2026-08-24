def summarize_weekly_context(df):
    if df.empty or len(df) < 2:
        return {
            "data_available": False,
            "period_start": None,
            "period_end": None,
            "open": 0.0,
            "close": 0.0,
            "week_high": 0.0,
            "week_low": 0.0,
            "week_change_pct": 0.0,
            "week_range_pct": 0.0,
            "avg_volume": 0.0,
            "last_24h_change_pct": 0.0,
        }

    first = df.iloc[0]
    last = df.iloc[-1]
    open_price = float(first["Open"])
    close_price = float(last["Close"])
    high = float(df["High"].max())
    low = float(df["Low"].min())

    change_pct = ((close_price - open_price) / open_price) * 100 if open_price else 0.0
    range_pct = ((high - low) / open_price) * 100 if open_price else 0.0
    avg_volume = float(df["Volume"].mean())

    last_24h = df.tail(24) if len(df) >= 24 else df
    last_24h_open = float(last_24h.iloc[0]["Open"])
    last_24h_close = float(last_24h.iloc[-1]["Close"])
    last_24h_change_pct = ((last_24h_close - last_24h_open) / last_24h_open) * 100 if last_24h_open else 0.0

    return {
        "data_available": True,
        "period_start": str(first["Timestamp"]),
        "period_end": str(last["Timestamp"]),
        "open": round(open_price, 4),
        "close": round(close_price, 4),
        "week_high": round(high, 4),
        "week_low": round(low, 4),
        "week_change_pct": round(change_pct, 3),
        "week_range_pct": round(range_pct, 3),
        "avg_volume": round(avg_volume, 3),
        "last_24h_change_pct": round(last_24h_change_pct, 3),
    }
