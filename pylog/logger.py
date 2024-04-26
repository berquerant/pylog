from dataclasses import dataclass
from typing import Any, Callable, Optional, Union


@dataclass(frozen=True)
class Event:
    """
    A log event.

        >>> from pylog.logger import Event
        >>> ev = Event.new(level=10, fmt="msg")
        >>> ev.update(fmt="changed")
        Event(level=10, fmt='changed', args=(), kwargs=())
        >>> ev.update("first", fmt="changed {} {key}", key=42)
        Event(level=10, fmt='changed {} {key}', args=('first',), kwargs=(('key', 42),))
        >>> str(ev.update("first", fmt="changed {} {key}", key=42))
        'changed first 42'
    """

    level: int
    fmt: str
    args: tuple[Any, ...]
    kwargs: tuple[tuple[str, Any], ...]

    def update(self, *args, **kwargs) -> "Event":
        """Return a new `Event` of which properties are updated."""
        level = kwargs.pop("level", self.level)
        fmt = kwargs.pop("fmt", self.fmt)
        return Event.new(
            level,
            fmt,
            *(self.args + args),
            **(dict(self.kwargs) | kwargs),
        )

    @staticmethod
    def new(level: int, fmt: str, *args, **kwargs) -> "Event":
        """Return a new `Event`."""
        return Event(level, fmt, args, tuple((k, kwargs[k]) for k in sorted(kwargs)))

    @property
    def keywords(self) -> dict[str, Any]:
        """Kwargs as a dict."""
        return dict(self.kwargs)

    def __str__(self) -> str:  # noqa: D105
        return self.fmt.format(*self.args, **dict(self.kwargs))


MapperT = Union[Callable[[Event], Optional[Event]], Callable[[Event], None], Callable[[Event], Event]]


@dataclass
class Mapper:
    """
    Mapper converts and/or filters the log event.

        >>> from pylog.logger import Mapper, Event
        >>> ev = Event.new(10, "msg")
        >>> m = Mapper(lambda x: x.update(level=20))
        >>> m(ev)
        Event(level=20, fmt='msg', args=(), kwargs=())
        >>> m += lambda x: x.update(fmt="changed")  # add mapper
        >>> m(ev)
        Event(level=20, fmt='changed', args=(), kwargs=())
        >>> m += Mapper(lambda x: x.update(1))
        >>> m(ev)
        Event(level=20, fmt='changed', args=(1,), kwargs=())
        >>> m |= lambda x: None  # add mapper but ignore the result
        >>> m += lambda x: x
        >>> m(ev)
        Event(level=20, fmt='changed', args=(1,), kwargs=())
    """

    mapper: MapperT

    def next(self, mapper: MapperT, ignore_result=False) -> "Mapper":
        """
        Append a mapper.

        :ignore_result: ignore returned value of `mapper` if True
        """
        if ignore_result:

            def inner_ignore(ev: Event) -> Optional[Event]:
                r = self.mapper(ev)
                if r is None:
                    return None
                mapper(r)  # ignore result
                return r

            return Mapper(inner_ignore)

        def inner(ev: Event) -> Optional[Event]:
            r = self.mapper(ev)
            if r is None:
                return None
            return mapper(r)

        return Mapper(inner)

    def __call__(self, ev: Event) -> Optional[Event]:
        return self.mapper(ev)

    def __add__(self, other: Union[MapperT, "Mapper"]) -> "Mapper":  # noqa: D105
        if isinstance(other, Mapper):
            return self.next(other.mapper)
        return self.next(other)

    def __or__(self, other: Union[MapperT, "Mapper"]) -> "Mapper":  # noqa: D105
        if isinstance(other, Mapper):
            return self.next(other.mapper, ignore_result=True)
        return self.next(other, ignore_result=True)


class PutError(Exception):
    """Raised when some event caused an exception in Logger.put."""


@dataclass
class Logger:
    mapper: Mapper

    def put(self, level: int, fmt: str, *args, **kwargs) -> Optional[Event]:
        try:
            return self.mapper(Event.new(level, fmt, *args, **kwargs))
        except Exception as e:
            raise PutError() from e
