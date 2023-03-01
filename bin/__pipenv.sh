#!/bin/bash -e

PYTHON="/root/.pyenv/shims/python"
PIPENV="${PYTHON} -m pipenv"

eval "$(pyenv init -)"
$PIPENV sync --dev
"$@"
