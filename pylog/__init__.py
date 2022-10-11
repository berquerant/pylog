"""A light-weight wrapper of standard log.

Logging basic:

    >>> import logging
    >>> logging.basicConfig(level=logging.DEBUG)
    >>> import pylog
    >>> _ = pylog.info("msg")  # INFO:root:msg

Mapper:

    >>> import logging
    >>> logging.basicConfig(level=logging.DEBUG)
    >>> l = pylog.LoggingLogger(pylog.Mapper(lambda e: e.update(fmt=f"mapped {e.fmt}")) + pylog.LoggingLogger.consumer)
    >>> _ = l.info("msg")  # INFO:root:mapped msg

Filter:

    >>> import logging
    >>> logging.basicConfig(level=logging.DEBUG)
    >>> l = pylog.LoggingLogger(pylog.Mapper(lambda e: e if "target" in e.fmt else None) + pylog.LoggingLogger.consumer)
    >>> _ = l.info("msg")
    >>> _ = l.info("msg target")  # INFO:root:msg target

Using pylog.cli from the shell to process lines:

`x` is a line from stdin.

Map lines:
lambda_expr

    $ seq 3 | python -m pylog.cli 'f"10{x}"'
    101
    102
    103

Filter lines:
Bool expression and None filter a line.
True accepts a line, False and None rejects a line.

    $ seq 3 | python -m pylog.cli 'int(x) > 1'
    2
    3
    $ seq 3 | python -m pylog.cli 'x if int(x) > 1 else None'
    2
    3

Raise exception:
Exceptions are written to stderr.

    $ seq 3 | python -m pylog.cli 'x if int(x) > 1 else _raise(Exception(f"exception from {x}"))'
    exception from 1
    2
    3

Map + Filter:

    $ seq 10 | python -m pylog.cli 'int(x) & 1 == 1' 'int(x) * 1.5'
    1.5
    4.5
    7.5
    10.5
    13.5

Aggregate:
`-i` prepares variables and functions, they are registered in global symtable.
`-e` is evaluated after reading all lines.

    $ python -m pylog.cli 'add(x)' -i 'd=[]' 'def add(x):global d;d.append(int(x))' 'from math import sqrt' 'def sdev():m=sum(d)/len(d);v=sum((x-m)**2 for x in d)/len(d);return sqrt(v)' -e 'sdev()' <<EOS
    90
    80
    40
    60
    90
    EOS
    19.390719429665317
"""  # noqa: E501
import logging
from dataclasses import dataclass
from .logger import (  # noqa: F401
    Event,
    MapperT,
    Mapper,
    PutError,
    Logger,
)
from typing import Optional


@dataclass
class LoggingLogger(Logger):
    """Log a message with `logging`."""

    @staticmethod
    def consumer(ev: Event) -> Optional[Event]:
        """Write a log event with `logging`."""
        msg = str(ev)
        match ev.level:
            case logging.DEBUG:
                logging.debug(msg)
            case logging.INFO:
                logging.info(msg)
            case logging.WARNING:
                logging.warning(msg)
            case logging.ERROR:
                logging.error(msg)
            case logging.CRITICAL:
                logging.critical(msg)
            case _:
                pass
        return ev

    @classmethod
    def new(cls) -> "LoggingLogger":
        return LoggingLogger(Mapper(cls.consumer))

    def debug(self, fmt: str, *args, **kwargs) -> Optional[Event]:
        return self.put(logging.DEBUG, fmt, *args, **kwargs)

    def info(self, fmt: str, *args, **kwargs) -> Optional[Event]:
        return self.put(logging.INFO, fmt, *args, **kwargs)

    def warning(self, fmt: str, *args, **kwargs) -> Optional[Event]:
        return self.put(logging.WARNING, fmt, *args, **kwargs)

    def error(self, fmt: str, *args, **kwargs) -> Optional[Event]:
        return self.put(logging.ERROR, fmt, *args, **kwargs)

    def critical(self, fmt: str, *args, **kwargs) -> Optional[Event]:
        return self.put(logging.CRITICAL, fmt, *args, **kwargs)


Default = LoggingLogger.new()
debug = Default.debug
info = Default.info
warning = Default.warning
error = Default.error
critical = Default.critical
