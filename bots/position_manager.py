from dataclasses import dataclass


@dataclass(frozen=True)
class ExitDecision:
    should_exit: bool
    reason: str


def check_exit(bot, position, current_price):
    if position.base_amount <= 0 or position.average_entry_price <= 0:
        return ExitDecision(False, "")

    change_pct = ((current_price - position.average_entry_price) / position.average_entry_price) * 100

    if change_pct <= -bot.stop_loss_pct:
        return ExitDecision(True, f"Stop-loss hit at {change_pct:+.2f}%.")

    if bot.trailing_stop_pct and position.peak_price > 0 and change_pct > 0:
        drawdown_from_peak_pct = ((current_price - position.peak_price) / position.peak_price) * 100

        if drawdown_from_peak_pct <= -bot.trailing_stop_pct:
            return ExitDecision(
                True, f"Trailing stop hit ({drawdown_from_peak_pct:+.2f}% off peak ${position.peak_price:,.2f})."
            )

    if bot.take_profit_pct and change_pct >= bot.take_profit_pct:
        return ExitDecision(True, f"Take-profit hit at {change_pct:+.2f}%.")

    return ExitDecision(False, "")
