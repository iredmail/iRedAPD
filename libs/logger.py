import os
import time
import zipfile
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import settings


# Extend original RotatingFileHandler to compress rotated log file.
class CompressedRotatingFileHandler(RotatingFileHandler):
    def doRollover(self):
        """
        Do a rollover, as described in __init__().
        """
        if self.stream:
            self.stream.close()
            self.stream = None
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = "%s.%d" % (self.baseFilename, i)
                dfn = "%s.%d" % (self.baseFilename, i + 1)
                if os.path.exists(sfn):
                    #print "%s -> %s" % (sfn, dfn)
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    os.rename(sfn, dfn)
            dfn = self.baseFilename + ".1"
            if os.path.exists(dfn):
                os.remove(dfn)
            # Issue 18940: A file may not have been created if delay is True.
            if os.path.exists(self.baseFilename):
                os.rename(self.baseFilename, dfn)
        try:
            if not self.delay:
                self.stream = self._open()
        except:
            self.stream = self._open()

        # Compress rotated log file.
        if os.path.exists(dfn + ".zip"):
            os.remove(dfn + ".zip")

        f = zipfile.ZipFile(dfn + ".zip", "w")
        f.write(dfn, os.path.basename(dfn), zipfile.ZIP_DEFLATED)
        f.close()
        os.remove(dfn)


# Extend original TimedRotatingFileHandler to compress rotated log file.
class CompressedTimedRotatingFileHandler(TimedRotatingFileHandler):
    def doRollover(self):
        """
        do a rollover; in this case, a date/time stamp is appended to the filename
        when the rollover happens.  However, you want the file to be named for the
        start of the interval, not the current time.  If there is a backup count,
        then we have to get a list of matching filenames, sort them and remove
        the one with the oldest suffix.
        """
        if self.stream:
            self.stream.close()
            self.stream = None
        # get the time that this sequence started at and make it a TimeTuple
        currentTime = int(time.time())
        dstNow = time.localtime(currentTime)[-1]
        t = self.rolloverAt - self.interval
        if self.utc:
            timeTuple = time.gmtime(t)
        else:
            timeTuple = time.localtime(t)
            dstThen = timeTuple[-1]
            if dstNow != dstThen:
                if dstNow:
                    addend = 3600
                else:
                    addend = -3600
                timeTuple = time.localtime(t + addend)
        dfn = self.baseFilename + "." + time.strftime(self.suffix, timeTuple)
        if os.path.exists(dfn):
            os.remove(dfn)
        # Issue 18940: A file may not have been created if delay is True.
        if os.path.exists(self.baseFilename):
            os.rename(self.baseFilename, dfn)
        if self.backupCount > 0:
            for s in self.getFilesToDelete():
                os.remove(s)

        try:
            if not self.delay:
                self.stream = self._open()
        except:
            self.stream = self._open()
        newRolloverAt = self.computeRollover(currentTime)
        while newRolloverAt <= currentTime:
            newRolloverAt = newRolloverAt + self.interval
        #If DST changes and midnight or weekly rollover, adjust for this.
        if (self.when == 'MIDNIGHT' or self.when.startswith('W')) and not self.utc:
            dstAtRollover = time.localtime(newRolloverAt)[-1]
            if dstNow != dstAtRollover:
                if not dstNow:  # DST kicks in before next rollover, so we need to deduct an hour
                    addend = -3600
                else:           # DST bows out before next rollover, so we need to add an hour
                    addend = 3600
                newRolloverAt += addend
        self.rolloverAt = newRolloverAt

        # Compress rotated log file.
        if os.path.exists(dfn + ".zip"):
            os.remove(dfn + ".zip")

        f = zipfile.ZipFile(dfn + ".zip", "w")
        f.write(dfn, os.path.basename(dfn), zipfile.ZIP_DEFLATED)
        f.close()
        os.remove(dfn)


logger = logging.getLogger('iRedAPD')

# Set log level.
log_level = getattr(logging, str(settings.log_level).upper())
logger.setLevel(log_level)

if settings.LOGROTATE_TYPE == 'size':
    # Rotate when file reaches 100MB (100*1024*1024), and save 10 backup copies.
    handler = CompressedRotatingFileHandler(filename=settings.log_file,
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

    handler = CompressedTimedRotatingFileHandler(filename=settings.log_file,
                                                 when=when,
                                                 interval=interval,
                                                 backupCount=settings.LOGROTATE_COPIES)

formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s', '%Y-%m-%d %H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)
