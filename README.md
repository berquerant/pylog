# pylog

A light-weight wrapper of standard log.

## Library

``` python
import pylog
import logging

logging.basicConfig(level=logging.DEBUG)
pylog.info("msg")

m = pylog.Mapper(lambda e: e.update(fmt=f"mapped {e.fmt}")) + pylog.LoggingLogger.consumer
pylog.LoggingLogger(m).info("msg")


def print_event(ev: pylog.Event):
    print(str(ev))


m += print_event
pylog.LoggingLogger(m).info("print ev")
# Output:
# INFO:root:msg
# INFO:root:mapped msg
# INFO:root:mapped print ev
# mapped print ev
```

## CLI

``` shell
$ seq 0 3 | python -m pylog.cli 'datetime(2022,10,11,hour=12)+timedelta(hours=int(x))' -i 'from datetime import datetime,timedelta'
2022-10-11 12:00:00
2022-10-11 13:00:00
2022-10-11 14:00:00
2022-10-11 15:00:00
```

Help: `python -m pylog.cli -h`

## Dev

``` bash
./bin/build_docker.sh
# run test
./bin/pipenv.sh make test
```
