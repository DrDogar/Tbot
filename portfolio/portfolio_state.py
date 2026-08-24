from dataclasses import dataclass, field


@dataclass
class Position:
    base_amount: float = 0.0
    average_entry_price: float = 0.0
    peak_price: float = 0.0


@dataclass
class TradeRecord:
    timestamp: str
    symbol: str
    side: str
    price: float
    base_amount: float
    quote_amount: float
    fee_quote: float
    reasoning: str


@dataclass
class PortfolioState:
    quote_balance: float
    starting_quote_balance: float
    positions: dict = field(default_factory=dict)
    trade_log: list = field(default_factory=list)
    realized_pnl: float = 0.0
    total_fees_paid: float = 0.0


def new_portfolio(symbols, starting_quote_balance):
    return PortfolioState(
        quote_balance=starting_quote_balance,
        starting_quote_balance=starting_quote_balance,
        positions={symbol: Position() for symbol in symbols},
    )


def get_position(state, symbol):
    return state.positions.setdefault(symbol, Position())


def apply_fill(state, symbol, plan, timestamp):
    position = get_position(state, symbol)

    if plan.side == "BUY":
        was_flat = position.base_amount <= 0
        state.quote_balance -= plan.quote_amount
        new_total_base = position.base_amount + plan.base_amount

        if new_total_base > 0:
            position.average_entry_price = (
                (position.average_entry_price * position.base_amount) + (plan.price * plan.base_amount)
            ) / new_total_base

        position.base_amount = new_total_base
        position.peak_price = plan.price if was_flat else max(position.peak_price, plan.price)

    elif plan.side == "SELL":
        proceeds = plan.quote_amount
        cost_basis = position.average_entry_price * plan.base_amount

        state.realized_pnl += proceeds - cost_basis
        state.quote_balance += proceeds
        position.base_amount = max(position.base_amount - plan.base_amount, 0.0)

        if position.base_amount <= 0:
            position.average_entry_price = 0.0
            position.peak_price = 0.0

    state.total_fees_paid += plan.fee_quote
    state.trade_log.append(
        TradeRecord(
            timestamp=timestamp,
            symbol=symbol,
            side=plan.side,
            price=plan.price,
            base_amount=plan.base_amount,
            quote_amount=plan.quote_amount,
            fee_quote=plan.fee_quote,
            reasoning=plan.reason,
        )
    )

    return state
