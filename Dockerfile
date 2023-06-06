# Dockerfile for creating containers running dqmsquare_mirror instances.

FROM python:3.9

RUN apt update \
    &&  apt upgrade -y \
    && apt-get update --fix-missing \
    && apt install -y libgtk-3-0 iputils-ping sqlite3 sudo nano postgresql python3-psycopg2

# setup postgres db
RUN echo "local   all             all                                     trust" >> /etc/postgresql/13/main/pg_hba.conf \
    && echo "data_directory='/cinder/dqmsquare/pgdb'"  >>  /etc/postgresql/13/main/postgresql.conf
 


COPY . /dqmsquare_mirror
WORKDIR dqmsquare_mirror

RUN python3 -m pip install -U pip \
  && python3 -m pip install -r requirements.txt \
  && mkdir -p /dqmsquare_mirror/log

# Add bottle
# RUN set -x \
#  && mkdir -p "bottle" \
#  && cd "bottle" \
#  && curl -sSLO https://github.com/bottlepy/bottle/archive/refs/tags/${BOTTLE_VER}.tar.gz \
#  && tar -xvzf ${BOTTLE_VER}.tar.gz \
#  && cp bottle-${BOTTLE_VER}/bottle.py .

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





