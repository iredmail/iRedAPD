import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import settings

logger = logging.getLogger('iRedAPD')

# Get log level.
log_level = getattr(logging, str(settings.log_level).upper())

logger.setLevel(log_level)

if settings.LOGROTATE_TYPE == 'size':
    # Rotate when file reaches 100MB (100*1024*1024), and save 10 backup copies.
    handler = RotatingFileHandler(filename=settings.log_file,
                                  mode='a',
                                  maxBytes=settings.LOGROTATE_SIZE,
                                  backupCount=settings.LOGROTATE_COPIES)
else:
    # settings.LOGROTATE_TYPE == 'time'
    (interval, when) = settings.LOGROTATE_INTERVAL.split('-', 1)

    if interval.isdigit():
        interval = int(interval)
    else:
        interval = 1

    handler = TimedRotatingFileHandler(filename=settings.log_file,
                                       when=when,
                                       interval=interval,
                                       backupCount=settings.LOGROTATE_COPIES)

formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s', '%Y-%m-%d %H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)
