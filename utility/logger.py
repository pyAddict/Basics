from logging import getLogger, Formatter, StreamHandler, INFO, DEBUG
from logging.handlers import RotatingFileHandler
from sys import stdout

from utility.config import LOG_FORMAT, LOG_FILE

DEFAULT_LOG_LEVEL = INFO
RF_HANDLER_LEVEL = INFO
STREAM_HANDLER_LEVEL = DEBUG
LOG_FILE_SIZE = 1024 * 1024 * 8
BACKUP_COUNT = 5

LOGGER_NAME = 'BASICS'


def initialize_logger(logger_name):
    logger = getLogger(logger_name)
    logger.setLevel(DEFAULT_LOG_LEVEL)
    fmt = Formatter(LOG_FORMAT)

    # ---------------Adding File Handler--------------------
    fh = RotatingFileHandler(LOG_FILE,
                             maxBytes=LOG_FILE_SIZE,
                             backupCount=BACKUP_COUNT)
    fh.setLevel(RF_HANDLER_LEVEL)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # -----------------Adding Stream Handler-----------------
    sh = StreamHandler(stdout)
    sh.setFormatter(fmt)
    sh.setLevel(STREAM_HANDLER_LEVEL)
    logger.addHandler(sh)

    return logger


logger = initialize_logger(LOGGER_NAME)