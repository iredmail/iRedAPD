import logging
from logging import StreamHandler
from logging.handlers import SysLogHandler
import settings

# Set application name.
logger = logging.getLogger('iredapd')

# Set log level.
_log_level = getattr(logging, str(settings.log_level).upper())
logger.setLevel(_log_level)

# Log format
_formatter = logging.Formatter('%(name)s %(levelname)s: %(message)s')

# Syslog handler
if settings.SYSLOG_SERVER.startswith('/'):
    # Log to a local socket
    _handler = SysLogHandler(address=settings.SYSLOG_SERVER,
                             facility=settings.SYSLOG_FACILITY)
else:
    # Log to a network address
    _handler = SysLogHandler(address=(settings.SYSLOG_SERVER, settings.SYSLOG_PORT),
                             facility=settings.SYSLOG_FACILITY)

_handler.setFormatter(_formatter)
logger.addHandler(_handler)


if settings.DEBUG:
    _steam_handler = StreamHandler()
    _steam_handler.setFormatter(_formatter)
    logger.addHandler(_steam_handler)
