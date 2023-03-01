FROM docker-ubuntu-latest-pyenv-git

RUN pyenv install "3.10"

RUN pyenv global "3.10" &&\
    eval "$(pyenv init -)" &&\
    python -m pip install pip --upgrade && \
    python -m pip install pipenv
