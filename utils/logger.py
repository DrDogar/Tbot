import logging

from config.settings import STATE_DIR

LOG_PATH = STATE_DIR / "session.log"


def get_logger():
    logger = logging.getLogger("tbot")

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
