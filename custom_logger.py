import logging
from logging.handlers import TimedRotatingFileHandler


### get logger ===>
def dummy_log():
    class DummyLogger:
        def info(self, text):
            print(text)

        def warning(self, text):
            print(text)

        def debug(self, text):
            print(text)

        def error(self, text):
            print(text)

    return DummyLogger()


def set_log_handler(logger, path, interval, nlogs, debug_level):
    try:
        # add a rotating handler
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler = TimedRotatingFileHandler(
            path, when="h", interval=int(interval), backupCount=int(nlogs)
        )
        handler.setFormatter(formatter)
        handler.setLevel(logging.DEBUG if debug_level else logging.INFO)
        logger.setLevel(logging.DEBUG if debug_level else logging.INFO)

        logger.addHandler(handler)
        logger.info(f"Logging started in '{path}'")
    except Exception as e:
        # print("!!!", repr(e))
        return dummy_log()
