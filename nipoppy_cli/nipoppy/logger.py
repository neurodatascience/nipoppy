"""Logger."""

import logging
from functools import partial
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

from nipoppy.env import StrOrPathLike

DATE_FORMAT = "[%Y-%m-%d %X]"
FORMAT_RICH = "%(message)s"
FORMAT_FILE = "%(asctime)s %(levelname)-7s %(message)s"


def get_logger(
    name: Optional[str] = "nipoppy", level: int = logging.INFO
) -> logging.Logger:
    """Create/get a logger with rich formatting."""
    # create logger
    logger = logging.getLogger(name=name)
    logger.setLevel(level)

    # partially instantiate RichHandler
    rich_handler = partial(
        RichHandler,
        show_time=False,
        markup=True,
        rich_tracebacks=True,
    )

    # stream WARNING and above to stderr with rich formatting
    stderr_handler = rich_handler(console=Console(stderr=True))
    stderr_handler.addFilter(lambda record: record.levelno >= logging.WARNING)
    logger.addHandler(stderr_handler)

    # stream levels below WARNING to stdout with rich formatting
    stdout_handler = rich_handler(console=Console(stderr=False))
    stdout_handler.addFilter(lambda record: record.levelno < logging.WARNING)
    logger.addHandler(stdout_handler)

    return logger


def add_logfile(logger: logging.Logger, fpath_log: StrOrPathLike) -> None:
    """Add a file handler to the logger."""
    fpath_log: Path = Path(fpath_log)

    dpath_log = fpath_log.parent
    if not dpath_log.exists():
        logger.warning(f"Creating log directory because it does not exist: {dpath_log}")
        dpath_log.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(fpath_log)
    file_handler.setFormatter(logging.Formatter(FORMAT_FILE, datefmt=DATE_FORMAT))
    logger.addHandler(file_handler)
    logger.info(f"Writing the log to {fpath_log}")
    return logger


def capture_warnings(logger: logging.Logger) -> logging.Logger:
    """
    Capture warnings and log them to the same places as a reference logger.

    Note that logging.captureWarnings(True) must be called before this function.

    Parameters
    ----------
    logger : logging.Logger
        The reference logger, whose handlers will be added the the warnings logger

    Returns
    -------
    logging.Logger
        The warning logger
    """
    warnings_logger = logging.getLogger("py.warnings")
    for handler in logger.handlers:
        if handler not in warnings_logger.handlers:
            warnings_logger.addHandler(handler)
    return warnings_logger
