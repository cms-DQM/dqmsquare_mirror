# Dockerfile for creating containers running dqmsquare_mirror instances.

FROM python:3.12-alpine

COPY . /dqmsquare_mirror
WORKDIR dqmsquare_mirror

# set CERN time zone
ENV TZ="Europe/Zurich"

RUN apk add build-base

# add new user switch to user
RUN apk update \
    && apk upgrade \
    && apk add --no-cache libpq bash

RUN python3 -m pip install -r requirements.txt

# Entrypoint, will be replaced with the one listed here:
# https://github.com/dmwm/CMSKubernetes/blob/master/kubernetes/cmsweb/services/dqmsquare.yaml
CMD ["/bin/bash"]