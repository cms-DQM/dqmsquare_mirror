# Dockerfile for creating containers running dqmsquare_mirror instances.

FROM python:3.11

COPY . /dqmsquare_mirror
WORKDIR dqmsquare_mirror

# set CERN time zone
ENV TZ="Europe/Zurich"

# add new user switch to user
RUN apt update \
    && apt upgrade -y \
    && apt-get update --fix-missing \
    && apt install -y python3-psycopg2 python3-pip

RUN python3 -m pip install -r requirements.txt

RUN useradd dqm \
    && mkdir -p /dqmsquare_mirror/log \
    && mkdir -p /home/dqm/ \
    && chown -R dqm /home/dqm/ \
    && find /dqmsquare_mirror -type d -exec chown -R dqm {} \; \
    && find /dqmsquare_mirror -type f -exec chown -R dqm {} \;
USER dqm

# Entrypoint, will be replaced with the one listed here:
# https://github.com/dmwm/CMSKubernetes/blob/master/kubernetes/cmsweb/services/dqmsquare.yaml
CMD ["/bin/bash"]