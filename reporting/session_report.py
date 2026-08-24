from config.settings import STATE_DIR
from portfolio.valuation import compute_portfolio_summary


def generate_report(portfolio, run_state):
    if portfolio is None or run_state is None:
        print("\nNo session state found yet.")
        return None

    summary = compute_portfolio_summary(portfolio)
    market_value = summary["market_value"]
    equity = summary["equity"]
    pnl = summary["pnl"]
    pnl_pct = summary["pnl_pct"]

    lines = []
    lines.append("=" * 55)
    lines.append("        TBOT 24H MULTI-COIN SESSION REPORT")
    lines.append("=" * 55)
    lines.append(f"Run ID           : {run_state.run_id}")
    lines.append(f"Started At (UTC) : {run_state.started_at}")
    lines.append(f"Cycles Run       : {run_state.cycle_count}")
    lines.append(f"Completed        : {'YES' if run_state.completed else 'NO'}")
    lines.append("-" * 55)
    lines.append(f"Starting Balance : ${portfolio.starting_quote_balance:,.2f}")
    lines.append(f"Cash (Quote)     : ${portfolio.quote_balance:,.2f}")
    lines.append(f"Open Positions   : ${market_value:,.2f}")
    lines.append(f"Total Equity     : ${equity:,.2f}")
    lines.append(f"Realized PnL     : ${portfolio.realized_pnl:,.2f}")
    lines.append(f"Total PnL        : ${pnl:,.2f} ({pnl_pct:+.2f}%)")
    lines.append(f"Total Fees Paid  : ${portfolio.total_fees_paid:,.2f}")
    lines.append(f"Total Trades     : {len(portfolio.trade_log)}")
    lines.append("-" * 55)

    for symbol, position in portfolio.positions.items():
        symbol_trades = [trade for trade in portfolio.trade_log if trade.symbol == symbol]
        lines.append(
            f"{symbol:10s} | trades={len(symbol_trades):3d} | holding={position.base_amount:.6f} "
            f"| avg_entry=${position.average_entry_price:,.4f}"
        )

    lines.append("=" * 55)

    report_text = "\n".join(lines)
    print("\n" + report_text)

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    report_path = STATE_DIR / f"report_{run_state.run_id}.txt"
    report_path.write_text(report_text, encoding="utf-8")

    print(f"\nSaved report to {report_path}")

    return report_text
