from config.settings import DECISION_ENGINE, STATE_DIR, WEB_MONITOR_HOST, WEB_MONITOR_PORT
from dashboard.web_server import run_web_monitor
from engine.runner import run_multi_coin_session
from engine.session_state import load_run_state
from portfolio.persistence import load_portfolio_state
from reporting.session_report import generate_report

RUN_STATE_PATH = STATE_DIR / "run_state.json"
PORTFOLIO_STATE_PATH = STATE_DIR / "portfolio_state.json"


def start_multi_coin_session():
    print("\n====================================")
    print("   24H MULTI-COIN TRADING SESSION")
    print("====================================")
    print(f"Decision engine : {DECISION_ENGINE}")
    print("Running in the foreground. Press Ctrl+C to stop early (progress is saved).")
    print("For an unattended 24h run, use 'python run_session.py' instead.\n")

    try:
        run_multi_coin_session()
    except KeyboardInterrupt:
        print("\nSession paused. Progress has been saved and will resume next time you start it.")


def show_session_report():
    run_state = load_run_state(RUN_STATE_PATH)
    portfolio = load_portfolio_state(PORTFOLIO_STATE_PATH)

    if run_state is None:
        print("\nNo session has been started yet.")
        return

    generate_report(portfolio, run_state)


def start_web_monitor():
    print("\n====================================")
    print("        TBOT WEB MONITOR")
    print("====================================")
    print(f"Open http://{WEB_MONITOR_HOST}:{WEB_MONITOR_PORT} in your browser.")
    print("Press Ctrl+C to stop the monitor (the trading session keeps running).\n")

    try:
        run_web_monitor()
    except KeyboardInterrupt:
        print("\nWeb monitor stopped.")
