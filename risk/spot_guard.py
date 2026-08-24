from dataclasses import dataclass

from config.settings import (
    MAX_TRADE_QUOTE_AMOUNT,
    MIN_QUOTE_BALANCE_BUFFER,
    PAPER_BASE_BALANCE,
    PAPER_QUOTE_BALANCE,
    SCALP_TRADE_QUOTE_AMOUNT,
    SPOT_ONLY,
    TAKER_FEE_PCT,
    TRADE_MODE,
)


@dataclass(frozen=True)
class SpotAccountSnapshot:
    base_free: float
    quote_free: float


@dataclass(frozen=True)
class TradePlan:
    allowed: bool
    mode: str
    symbol: str
    side: str
    quote_amount: float
    base_amount: float
    price: float
    fee_quote: float
    reason: str


def get_paper_account_snapshot():
    return SpotAccountSnapshot(
        base_free=PAPER_BASE_BALANCE,
        quote_free=PAPER_QUOTE_BALANCE,
    )


def build_spot_trade_plan(signal, symbol, account=None, quote_amount=None, fee_pct=TAKER_FEE_PCT):
    account = account or get_paper_account_snapshot()

    if not SPOT_ONLY:
        return _blocked(signal, symbol, quote_amount or 0.0, 0.0, 0.0, "Spot-only mode is disabled.")

    if signal.action == "HOLD":
        return _blocked(signal, symbol, 0.0, 0.0, 0.0, signal.reason)

    if signal.action == "BUY":
        # Capped: an entry should never risk more than MAX_TRADE_QUOTE_AMOUNT in one trade.
        buy_quote_amount = min(quote_amount or SCALP_TRADE_QUOTE_AMOUNT, MAX_TRADE_QUOTE_AMOUNT)
        spendable_quote = max(account.quote_free - MIN_QUOTE_BALANCE_BUFFER, 0.0)

        if spendable_quote < buy_quote_amount:
            return _blocked(
                signal,
                symbol,
                buy_quote_amount,
                0.0,
                0.0,
                "Not enough quote balance after safety buffer.",
            )

        fee_quote = buy_quote_amount * fee_pct
        base_amount = (buy_quote_amount - fee_quote) / signal.price if signal.price else 0.0

        return TradePlan(
            allowed=True,
            mode=TRADE_MODE,
            symbol=symbol,
            side="BUY",
            quote_amount=buy_quote_amount,
            base_amount=base_amount,
            price=signal.price,
            fee_quote=fee_quote,
            reason=signal.reason,
        )

    if signal.action == "SELL":
        if account.base_free <= 0:
            return _blocked(
                signal,
                symbol,
                quote_amount or 0.0,
                0.0,
                0.0,
                "Spot guard blocked SELL because no base asset is available. No short selling.",
            )

        # Not clamped to MAX_TRADE_QUOTE_AMOUNT: an exit (stop-loss/take-profit) must always be
        # able to fully close a position, however large, or the risk cap it enforces is a lie.
        sell_quote_amount = quote_amount or SCALP_TRADE_QUOTE_AMOUNT
        desired_base_amount = sell_quote_amount / signal.price if signal.price else 0.0
        sell_base_amount = min(account.base_free, desired_base_amount)
        gross_quote = sell_base_amount * signal.price
        fee_quote = gross_quote * fee_pct
        net_quote = gross_quote - fee_quote

        return TradePlan(
            allowed=True,
            mode=TRADE_MODE,
            symbol=symbol,
            side="SELL",
            quote_amount=net_quote,
            base_amount=sell_base_amount,
            price=signal.price,
            fee_quote=fee_quote,
            reason=signal.reason,
        )

    return _blocked(signal, symbol, 0.0, 0.0, 0.0, "Unknown strategy action.")


def _blocked(signal, symbol, quote_amount, base_amount, fee_quote, reason):
    return TradePlan(
        allowed=False,
        mode=TRADE_MODE,
        symbol=symbol,
        side=signal.action,
        quote_amount=quote_amount,
        base_amount=base_amount,
        price=signal.price,
        fee_quote=fee_quote,
        reason=reason,
    )
