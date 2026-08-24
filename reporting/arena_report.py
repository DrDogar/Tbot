from config.settings import STATE_DIR
from portfolio.valuation import compute_portfolio_summary


def generate_arena_report(bots, portfolios, run_state):
    if run_state is None or not portfolios:
        print("\nNo arena state found yet.")
        return None

    lines = []
    lines.append("=" * 60)
    lines.append(f"           TBOT {len(bots)}-BOT ARENA SESSION REPORT")
    lines.append("=" * 60)
    lines.append(f"Run ID           : {run_state.run_id}")
    lines.append(f"Started At (UTC) : {run_state.started_at}")
    lines.append(f"Cycles Run       : {run_state.cycle_count}")
    lines.append(f"Completed        : {'YES' if run_state.completed else 'NO'}")
    lines.append("-" * 60)

    results = []
    for bot in bots:
        portfolio = portfolios.get(bot.key)

        if portfolio is None:
            continue

        summary = compute_portfolio_summary(portfolio)
        results.append((bot, portfolio, summary))

    results.sort(key=lambda item: item[2]["pnl_pct"], reverse=True)

    for rank, (bot, portfolio, summary) in enumerate(results, start=1):
        lines.append(
            f"#{rank} {bot.name:25s} | equity=${summary['equity']:,.2f} "
            f"| pnl={summary['pnl']:+,.2f} ({summary['pnl_pct']:+.2f}%) "
            f"| trades={len(portfolio.trade_log):3d} | fees=${portfolio.total_fees_paid:,.2f}"
        )

    lines.append("=" * 60)

    report_text = "\n".join(lines)
    print("\n" + report_text)

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    report_path = STATE_DIR / f"arena_report_{run_state.run_id}.txt"
    report_path.write_text(report_text, encoding="utf-8")

    print(f"\nSaved arena report to {report_path}")

    return report_text
