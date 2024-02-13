import logging
from pathlib import Path

DEFAULT_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)-7s - %(message)s'

def create_logger(name: str, fpath=None, format=None, level=logging.DEBUG) -> logging.Logger:
    
    if format is None:
        format = DEFAULT_LOG_FORMAT

    # get the logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # always output to terminal
    stream_handler = logging.StreamHandler()
    stream_formatter = logging.Formatter(format)
    stream_handler.setFormatter(stream_formatter)
    logger.addHandler(stream_handler)

    # output to file if fpath is provided
    if fpath is not None:

        fpath = Path(fpath)
        fpath.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(fpath)
        file_formatter = logging.Formatter(format)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        logger.info(f'Writing log to file: {fpath}')

    else:
        logger.warning('No path provided for logger, will not write to a log file.')

    return logger
