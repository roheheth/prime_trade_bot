"""
logging_config.py
-----------------
Sets up dual-channel logging: verbose DEBUG logs to a rotating file,
and WARNING+ to the console (so CLI output stays clean).
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

_loggers: dict = {}


def setup_logger(name: str = "trading_bot", log_dir: str = "logs") -> logging.Logger:
    """
    Returns a named logger. Calling this multiple times with the same
    name returns the same logger (no duplicate handlers).
    """
    if name in _loggers:
        return _loggers[name]

    os.makedirs(log_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(log_dir, f"bot_{date_str}.log")

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # ── File handler: DEBUG and above, rotating at 5 MB ──────────────
    fh = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(module)-20s:%(lineno)-4d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    # ── Console handler: WARNING and above only ───────────────────────
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    logger.addHandler(fh)
    logger.addHandler(ch)

    _loggers[name] = logger
    logger.info(f"Logger initialised | name={name} | file={log_file}")
    return logger
