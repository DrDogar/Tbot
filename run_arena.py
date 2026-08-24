import time

from dotenv import load_dotenv

load_dotenv()

from bots.runner import run_bot_arena
from utils.logger import get_logger

logger = get_logger()

if __name__ == "__main__":
    while True:
        try:
            run_bot_arena()
            break
        except Exception:
            logger.exception("Arena crashed. Restarting in 5s (resuming from last saved cycle)...")
            time.sleep(5)
