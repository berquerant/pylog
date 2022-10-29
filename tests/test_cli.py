from io import StringIO
from textwrap import dedent
from typing import Optional

import pytest

import pylog.cli as cli


@pytest.mark.parametrize(
    "args,want",
    [
        (
            ["x"],
            cli.Arguments(lambda_expr=["x"]),
        ),
        (
            ["x", "-i", "y=0"],
            cli.Arguments(lambda_expr=["x"], init=["y=0"]),
        ),
        (
            ["x", "-i", "y=0", "z=1"],
            cli.Arguments(lambda_expr=["x"], init=["y=0", "z=1"]),
        ),
        (
            ["x", "x**x", "-i", "y=0", "z=1", "-e", "f()"],
            cli.Arguments(lambda_expr=["x", "x**x"], init=["y=0", "z=1"], last="f()"),
        ),
    ],
)
def test_arguments_new(args: list[str], want: cli.Arguments):
    got = cli.Arguments.new(cli.new_parser().parse_args(args))
    assert want == got


@pytest.mark.parametrize(
    "title,init_list,expr_list,last_expr,lines,want,want_exc",
    [
        (
            "no exprs",
            [],
            [],
            None,
            [
                "first",
                "second",
                "third",
            ],
            dedent(
                """\
            first
            second
            third
            """
            ),
            [],
        ),
        (
            "an expr",
            [],
            [
                'f"mapped {x}"',
            ],
            None,
            [
                "first",
                "second",
                "third",
            ],
            dedent(
                """\
            mapped first
            mapped second
            mapped third
            """
            ),
            [],
        ),
        (
            "an expr return None",
            [],
            [
                'f"mapped {x}" if x != "second" else None',
            ],
            None,
            [
                "first",
                "second",
                "third",
            ],
            dedent(
                """\
            mapped first
            mapped third
            """
            ),
            [],
        ),
        (
            "an expr return bool",
            [],
            [
                'x != "second"',
            ],
            None,
            [
                "first",
                "second",
                "third",
            ],
            dedent(
                """\
            first
            third
            """
            ),
            [],
        ),
        (
            "an expr raise Exception",
            [],
            [
                'f"mapped {x}" if x != "second" else _raise(Exception(x))',
            ],
            None,
            [
                "first",
                "second",
                "third",
            ],
            dedent(
                """\
            mapped first
            mapped third
            """
            ),
            [
                Exception("lambda[0](('second',), {}) caused second"),
            ],
        ),
        (
            "2 exprs",
            [],
            [
                'f"mapped {x}" if x != "second" else _raise(Exception(x))',
                'f"second {x}"',
            ],
            None,
            [
                "first",
                "second",
                "third",
            ],
            dedent(
                """\
            second mapped first
            second mapped third
            """
            ),
            [
                Exception("lambda[0](('second',), {}) caused second"),
            ],
        ),
        (
            "linum",
            [
                "c = 0",
                dedent(
                    """\
            def cnt() -> int:
                global c
                c += 1
                return c
            """
                ),
            ],
            [
                'f"{cnt()}: {x}"',
            ],
            None,
            [
                "first",
                "second",
                "third",
            ],
            dedent(
                """\
            1: first
            2: second
            3: third
            """
            ),
            [],
        ),
        (
            "char count",
            [
                "c = 0",
                dedent(
                    """\
                def cnt(delta):
                    global c
                    c += delta
                    return c
                """
                ),
            ],
            [
                'f"{cnt(len(x))} {x}"',
            ],
            'f"count = {c}"',
            [
                "first",
                "second",
                "third",
            ],
            dedent(
                """\
                5 first
                11 second
                16 third
                count = 16
            """
            ),
            [],
        ),
        (
            "last lambda raises an exception",
            [
                "c = 0",
                dedent(
                    """\
                def cnt(delta):
                    global c
                    c += delta
                    return c
                """
                ),
            ],
            [
                'f"{cnt(len(x))} {x}"',
            ],
            'f"count = {C}"',
            [
                "first",
                "second",
                "third",
            ],
            dedent(
                """\
                5 first
                11 second
                16 third
            """
            ),
            [Exception("lambda[last]((), {}) caused name 'C' is not defined")],
        ),
        (
            "timedelta",
            [
                "from datetime import datetime, timedelta",
                "base = datetime(2022, 10, 10)",
            ],
            [
                "base + timedelta(hours=int(x))",
            ],
            None,
            [
                "0",
                "1",
                "4",
            ],
            dedent(
                """\
                2022-10-10 00:00:00
                2022-10-10 01:00:00
                2022-10-10 04:00:00
                """
            ),
            [],
        ),
    ],
)
def test_map_lines(
    title: str,
    init_list: list[str],
    expr_list: list[str],
    last_expr: Optional[str],
    lines: list[str],
    want: str,
    want_exc: list[Exception],
):
    got_exc: list[Exception] = []

    def on_exc(e: Exception):
        nonlocal got_exc
        got_exc.append(e)

    got = StringIO()
    cli.map_lines(expr_list, lines, got, on_exc, init_list, last_expr)

    assert want == got.getvalue()
    assert [str(x) for x in want_exc] == [str(x) for x in got_exc]
