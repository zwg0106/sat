import logging
from const import LOG_FILENAME, LOG_FILESIZE
from logging.handlers import RotatingFileHandler

def sat_logger():
    formatter = ("[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s")
    datefmt = '%Y-%m-%d %H:%M:%S'

    logging.basicConfig(level=logging.DEBUG, format=formatter, datefmt = datefmt, filename = LOG_FILENAME, filemode = 'w')

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(formatter))
    logging.getLogger(LOG_FILENAME).addHandler(handler)

    return logging.getLogger(LOG_FILENAME)

LOGGER=sat_logger()
