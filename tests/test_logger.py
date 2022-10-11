import pylog.logger as logger
from typing import Optional, Any

import pytest


class mockFunc:
    def __init__(self, ret: Optional[logger.Event] = None, exc: Optional[Exception] = None):
        self.args: list[logger.Event] = []
        self.ret = ret
        self.exc = exc

    def mapper(self, ev: logger.Event) -> Optional[logger.Event]:
        if self.exc is not None:
            raise self.exc
        self.args.append(ev)
        return self.ret


FIRST_EVENT = logger.Event.new(10, "first event")
SECOND_EVENT = logger.Event.new(10, "second event")


@pytest.mark.parametrize(
    "title,mappers,event,args_list,ret",
    [
        (
            "a mapper",
            [
                {
                    "ret": FIRST_EVENT,
                },
            ],
            FIRST_EVENT,
            [[FIRST_EVENT]],
            FIRST_EVENT,
        ),
        (
            "a mapper modify event",
            [
                {
                    "ret": SECOND_EVENT,
                },
            ],
            FIRST_EVENT,
            [[FIRST_EVENT]],
            SECOND_EVENT,
        ),
        (
            "two mappers",
            [
                {
                    "ret": SECOND_EVENT,
                },
                {
                    "ret": SECOND_EVENT,
                },
            ],
            FIRST_EVENT,
            [[FIRST_EVENT], [SECOND_EVENT]],
            SECOND_EVENT,
        ),
        (
            "two mappers filter event",
            [
                {},
                {
                    "ret": SECOND_EVENT,
                },
            ],
            FIRST_EVENT,
            [[FIRST_EVENT], []],
            None,
        ),
    ],
)
def test_mapper(
    title: str,
    mappers: list[dict[str, Any]],
    event: logger.Event,
    args_list: list[list[logger.Event]],
    ret: Optional[logger.Event],
):
    if not mappers:
        raise Exception("no mappers")
    funcs = [mockFunc(**x) for x in mappers]
    mapper = logger.Mapper(funcs[0].mapper)
    for f in funcs[1:]:
        mapper = mapper.next(f.mapper)

    assert ret == mapper(event)
    assert args_list == [x.args for x in funcs]


def test_logger_put_error():
    with pytest.raises(logger.PutError):
        logger.Logger(logger.Mapper(mockFunc(exc=Exception()).mapper)).put(10, "msg")
