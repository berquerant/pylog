#!/bin/bash -xe

docker build "github.com/berquerant/docker-ubuntu-latest-pyenv-git#v0.1.0" --tag docker-ubuntu-latest-pyenv-git
docker build . --tag pylog
