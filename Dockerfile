# Dockerfile for creating containers running dqmsquare_mirror instances.

FROM python:3.9

RUN apt update \
    && apt upgrade -y \
    && apt install -y lsb-release \
    && sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list' \
    && wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - \
    && apt-get update --fix-missing \
    && apt install -y libgtk-3-0 iputils-ping sudo nano postgresql-13 python3-psycopg2

# setup postgres db
RUN echo "local   all             all                                     trust" >> /etc/postgresql/13/main/pg_hba.conf \
    && echo "data_directory='/cinder/dqmsquare/pgdb'"  >>  /etc/postgresql/13/main/postgresql.conf
 
COPY . /dqmsquare_mirror
WORKDIR dqmsquare_mirror

RUN python3 -m pip install -U pip \
  && python3 -m pip install -r requirements.txt \
  && mkdir -p /dqmsquare_mirror/log

# set CERN time zone
ENV TZ="Europe/Zurich"

# add new user, add user to sudoers file, switch to user
RUN useradd dqm \
    && echo "%dqm ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers \
    && mkdir -p /home/dqm/ \
    && chmod 777 /home/dqm/ \
    && find /dqmsquare_mirror -type d -exec chmod 777 {} \; \ 
    && find /dqmsquare_mirror -type f -exec chmod 777 {} \; 
USER dqm
 
# Entrypoint, will be replaced with the one listed here:
# https://github.com/dmwm/CMSKubernetes/blob/master/kubernetes/cmsweb/services/dqmsquare.yaml
CMD ["/bin/bash"]





