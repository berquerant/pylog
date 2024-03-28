"""Entry point of CLI."""

import argparse
import logging
import sys
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from textwrap import dedent
from typing import Any, Callable, Iterator, NoReturn, Optional, ParamSpec, TextIO, TypeVar, cast


def _raise(exc: Exception) -> NoReturn:
    raise exc


__T = TypeVar("__T")
__P = ParamSpec("__P")


def __optional(f: Optional[Callable[__P, __T]]) -> Callable[__P, Optional[__T]]:
    match f:
        case None:

            def null(*args: __P.args, **kwargs: __P.kwargs) -> Optional[__T]:
                return None

            return null
        case _:
            g = cast(Callable[__P, __T], f)

            @wraps(g)
            def inner(*args: __P.args, **kwargs: __P.kwargs) -> Optional[__T]:
                return g(*args, **kwargs)

            return inner


def __watch(label: int | str, f: Callable[__P, __T]) -> Callable[__P, __T]:
    @wraps(f)
    def inner(*args: __P.args, **kwargs: __P.kwargs) -> __T:
        try:
            r = f(*args, **kwargs)
            logging.debug("%s(%s, %s) => %s", label, args, kwargs, r)
            return r
        except Exception as e:
            raise Exception(f"{label}({args}, {kwargs}) caused {e}") from e

    return inner


@dataclass
class Mapper:
    """Function to convert values and the symtable for the function."""

    function: Callable[[Any], Optional[Any]]
    symtable: dict[str, Any]
    last_function: Callable[[], Optional[Any]]

    @dataclass
    class Funcs:
        mapper: Callable[[Any], Optional[Any]]
        last_mapper: Callable[[], Optional[Any]]

        def __call__(self, x: Any) -> Optional[Any]:
            return self.mapper(x)

        def last(self) -> Optional[Any]:
            """Call `last_function` if exists."""
            r = self.last_mapper()
            if r is None:
                return None
            return str(r)

    @contextmanager
    def apply_symtable(self) -> Iterator[Funcs]:
        """Register symbols to call the function."""

        updated_keys = set(self.symtable.keys()) & set(globals().keys())
        if updated_keys:
            raise Exception(f"cannot update global symtable keys {updated_keys}")

        added_keys = set(self.symtable.keys()) - set(globals().keys())
        for k, v in self.symtable.items():  # update global symtable
            logging.debug("mapper symtable: %s => %s", k, v)
            globals()[k] = v
        yield self.Funcs(mapper=self.function, last_mapper=self.last_function)
        for k in added_keys:  # revert global symtable
            del globals()[k]


def new_mapper_chain(
    lambda_list: list[str],
    on_exception: Callable[[Exception], None],
    init_list: Optional[list[str]] = None,
    last_lambda: Optional[str] = None,
) -> Mapper:
    """
    Evaluate expressions and statements and generate `Mapper`.

    Invoke lambda_list in order.
    If the returned value is None or False, then terminate invocation.
    If the returned value is True, then invoke the next with the same str as the first.
    Otherwise invoke the next with the returned value.

    :lambda_list: expr list.
      The body of lambda, of which argument is `x`.
    :on_exception: receive an exception from lambda.
    :init_list: statement list.
      Evaluate only once the statements before evaluating lambda_list.
    :last_lambda: an expr.
      The body of lambda without arguments.
      The type of the expr sholud be str or None, otherwise expr value is casted to str.
    """
    local_table: dict[str, Any] = {}
    if init_list:
        for init in init_list:
            exec(init, globals(), local_table)

    functions = [
        __watch(f"lambda[{i}]", eval(f"lambda x: {x}", globals(), local_table)) for i, x in enumerate(lambda_list)
    ]
    last_function = cast(
        Optional[Callable[[], Any]],
        (
            None
            if last_lambda is None
            else __watch("lambda[last]", eval(f"lambda: {last_lambda}", globals(), local_table))
        ),
    )

    def inner(x: Any) -> Optional[Any]:
        for f in functions:
            try:
                match f(x):
                    case None | False:
                        return None
                    case True:
                        continue
                    case _x:
                        x = _x
            except Exception as e:
                on_exception(e)
                return None
        return x

    return Mapper(
        function=inner,
        symtable=local_table,
        last_function=__optional(last_function),
    )


def __map_lines(
    __lines: Iterator[str],
    __output: TextIO,
    __mapper: Mapper,
    __on_exception: Callable[[Exception], None],
):
    with __mapper.apply_symtable() as __f:
        for __line in __lines:
            __result = __f(__line.rstrip())
            if __result is not None:
                print(__result, file=__output)
        try:
            __result = __f.last()
            if __result is not None:
                print(__result, file=__output)
        except Exception as e:
            __on_exception(e)


def map_lines(
    lambda_list: list[str],
    lines: Iterator[str],
    output: TextIO,
    on_exception: Optional[Callable[[Exception], None]] = None,
    init_list: Optional[list[str]] = None,
    last_lambda: Optional[str] = None,
):
    on_exc: Callable[[Exception], None] = __optional(on_exception)
    __map_lines(
        lines,
        output,
        new_mapper_chain(lambda_list, on_exc, init_list, last_lambda),
        on_exc,
    )


def new_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=dedent(
            """\
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

            $ seq 3 | python -m pylog.cli 'int(x)>1'
            2
            3
            $ seq 3 | python -m pylog.cli 'x if int(x)>1 else None'
            2
            3

            Raise exception:
            Exceptions are written to stderr.

            $ seq 3 | python -m pylog.cli 'x if int(x)>1 else _raise(Exception(f"exception from {x}"))'
            lambda[0](('1',), {}) caused exception from 1
            2
            3

            Map + Filter:

            $ seq 10 | python -m pylog.cli 'int(x)&1==1' 'int(x)*1.5' 'x/1.5'
            1.0
            3.0
            5.0
            7.0
            9.0

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
        ),
    )
    parser.add_argument(
        "lambda_expr",
        type=str,
        nargs="+",
        help="expression for processing lines",
    )
    parser.add_argument("-i", "--init", type=str, nargs="*", help="statements for initialization")
    parser.add_argument("-e", "--last", type=str, help="expression for cleanup")
    parser.add_argument("-v", "--verbose", action="store_true", help="verbose logging")
    return parser


@dataclass
class Arguments:
    lambda_expr: list[str]
    init: Optional[list[str]] = None
    last: Optional[str] = None

    def run(self, lines: Iterator[str], output: TextIO, on_exception: Optional[Callable[[Exception], None]]) -> int:
        map_lines(self.lambda_expr, lines, output, on_exception, self.init, self.last)
        return 0

    @staticmethod
    def new(args: argparse.Namespace) -> "Arguments":
        logging.debug("init: %s", args.init)
        logging.debug("lambda[last]: %s", args.last)
        for i, x in enumerate(args.lambda_expr):
            logging.debug("lambda[%d]: %s", i, x)
        return Arguments(
            lambda_expr=args.lambda_expr,
            init=args.init,
            last=args.last,
        )


def main() -> int:
    """Entry point of CLI."""
    parser = new_parser()
    args = parser.parse_args()

    def on_exception(exc: Exception):
        if args.verbose:
            traceback.print_exception(exc)
        else:
            print(exc, file=sys.stderr)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s:%(message)s")

    return Arguments.new(args).run(sys.stdin, sys.stdout, on_exception)


if __name__ == "__main__":
    sys.exit(main())
