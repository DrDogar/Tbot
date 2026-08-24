from bots.bot_configs import BOTS
from bots.runner import ARENA_DIR, RUN_STATE_PATH, run_bot_arena
from config.settings import WEB_MONITOR_HOST, WEB_MONITOR_PORT
from engine.session_state import load_run_state
from portfolio.persistence import load_portfolio_state
from reporting.arena_report import generate_arena_report


def start_bot_arena():
    print("\n====================================")
    print(f"        TBOT {len(BOTS)}-BOT ARENA")
    print("====================================")
    print("Each bot gets its own $1,000 and trades all 5 coins with its own strategy:")

    for bot in BOTS:
        print(f" - {bot.name}: {bot.description}")

    print("\nTraining each bot on the last 7 days of data before going live...")
    print("Running in the foreground. Press Ctrl+C to stop early (progress is saved).")
    print(f"Watch it live at http://{WEB_MONITOR_HOST}:{WEB_MONITOR_PORT}/arena")
    print("For an unattended 24h run, use 'python run_arena.py' instead.\n")

    try:
        run_bot_arena()
    except KeyboardInterrupt:
        print("\nArena paused. Progress has been saved and will resume next time you start it.")


def show_arena_report():
    run_state = load_run_state(RUN_STATE_PATH)

    if run_state is None:
        print("\nNo arena session has been started yet.")
        return

    portfolios = {bot.key: load_portfolio_state(ARENA_DIR / f"portfolio_{bot.key}.json") for bot in BOTS}
    generate_arena_report(BOTS, portfolios, run_state)
