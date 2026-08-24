import time

from dotenv import load_dotenv

load_dotenv()

from config.settings import WEB_MONITOR_HOST, WEB_MONITOR_PORT
from dashboard.web_server import run_web_monitor
from utils.logger import get_logger

logger = get_logger()

if __name__ == "__main__":
    print(f"\nTBOT web monitor starting at http://{WEB_MONITOR_HOST}:{WEB_MONITOR_PORT}\n")

    while True:
        try:
            run_web_monitor()
            break
        except Exception:
            logger.exception("Web monitor crashed. Restarting in 5s...")
            time.sleep(5)
