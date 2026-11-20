import logging
import sys
from typing import Any, Dict


def setup_logging(debug: bool = False) -> logging.Logger:
    level = logging.DEBUG if debug else logging.INFO
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    logger = logging.getLogger("ubuntubiz")
    logger.setLevel(level)
    if not logger.handlers:
        logger.addHandler(handler)
    logger.propagate = False
    return logger


logger = setup_logging()
