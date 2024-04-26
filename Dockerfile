FROM docker-ubuntu-latest-pyenv-git

RUN pyenv install "3.11"

RUN pyenv global "3.11" &&\
    eval "$(pyenv init -)" &&\
    python -m pip install pip --upgrade && \
    python -m pip install pipenv
