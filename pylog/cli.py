"""Entry point of CLI."""
import sys
import argparse
from textwrap import dedent
from typing import Callable, Optional, Iterator, TextIO, Any
from dataclasses import dataclass
from contextlib import contextmanager
import logging


def _raise(exc: Exception):
    raise exc


@dataclass
class Mapper:
    """Function to convert a string and the symtable for the function."""

    function: Callable[[str], Optional[str]]
    symtable: dict[str, Any]
    last_function: Optional[Callable[[], Optional[Any]]] = None

    @contextmanager
    def apply_symtable(self):
        """Register symbols to call the function."""

        for k, v in self.symtable.items():
            logging.debug("mapper symtable: %s => %s", k, v)

        updated_keys = set(self.symtable.keys()) & set(globals().keys())
        if updated_keys:
            raise Exception(f"cannot update global symtable keys {updated_keys}")

        added_keys = set(self.symtable.keys()) - set(globals().keys())
        for k, v in self.symtable.items():  # update global symtable
            globals()[k] = v
        yield
        for k in added_keys:  # revert global symtable
            del globals()[k]

    def __call__(self, x: str) -> Optional[str]:
        return self.function(x)

    def last(self) -> Optional[str]:
        """Call `last_function` if exists."""
        if self.last_function:
            r = self.last_function()
            if r is None:
                return None
            return str(r)
        return None


def new_mapper_chain(
    lambda_list: list[str],
    on_exception: Optional[Callable[[Exception], None]] = None,
    init_list: Optional[list[str]] = None,
    last_lambda: Optional[str] = None,
) -> Mapper:
    """
    Evaluate expressions and statements and generate `Mapper`.

    Invoke lambda_list in order,
    invoke the next with the returned value if it's str.
    If the returned value is None or False, then terminate invocation.
    If the returned value is True, then invoke the next with the same str as the first.
    Otherwise the returned value is casted to str.

    :lambda_list: expr list.
      The body of lambda, of which argument is `x` of type str.
      The type of the expr should be str, None or bool.
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
    functions = [eval(f"lambda x: {x}", globals(), local_table) for x in lambda_list]

    def inner(x: str) -> Optional[str]:
        for i, f in enumerate(functions):
            try:
                _x = f(x)
                if isinstance(_x, str):  # convert line
                    x = _x
                    continue
                if _x is None:  # filter line
                    return None
                if isinstance(_x, bool):  # filter line
                    if _x:
                        continue
                    return None
                x = str(_x)
            except Exception as e:
                if on_exception:
                    on_exception(e)
                return None
        return x

    return Mapper(
        function=inner,
        symtable=local_table,
        last_function=None if last_lambda is None else eval(f"lambda: {last_lambda}", globals(), local_table),
    )


def __map_lines(__lines: Iterator[str], __output: TextIO, __mapper: Mapper):
    with __mapper.apply_symtable():
        for __line in __lines:
            __result = __mapper(__line.rstrip())
            if __result is not None:
                print(__result, file=__output)
        __result = __mapper.last()
        if __result is not None:
            print(__result, file=__output)


def map_lines(
    lambda_list: list[str],
    lines: Iterator[str],
    output: TextIO,
    on_exception: Optional[Callable[[Exception], None]] = None,
    init_list: Optional[list[str]] = None,
    last_lambda: Optional[str] = None,
):
    __map_lines(lines, output, new_mapper_chain(lambda_list, on_exception, init_list, last_lambda))


def main() -> int:
    """Entry point of CLI."""
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
        ),
    )
    parser.add_argument(
        "lambda_expr",
        type=str,
        nargs="*",
        help="expression for processing lines",
    )
    parser.add_argument("-i", "--init", type=str, nargs="*", help="statements for initialization")
    parser.add_argument("-e", "--last", type=str, help="expression for cleanup")
    parser.add_argument("-v", "--verbose", action="store_true", help="verbose logging")

    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    logging.debug("init: %s", args.init)
    logging.debug("last: %s", args.last)
    for x in args.lambda_expr:
        logging.debug("lambda: %s", x)
    map_lines(args.lambda_expr, sys.stdin, sys.stdout, lambda x: print(x, file=sys.stderr), args.init, args.last)
    return 0


if __name__ == "__main__":
    sys.exit(main())
