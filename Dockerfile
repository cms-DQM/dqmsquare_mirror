# Dockerfile for creating containers running dqmsquare_mirror instances.

FROM python:3.9.16

RUN apt update \
    &&  apt upgrade -y \
# && apt remove -y imagemagick-6-common libaom0 libbluetooth-dev libbluetooth3 libapparmor1 libcairo2 libcairo2-dev \
# && apt remove -y libnss3 libopenjp2-7 mariadb-common libctf-nobfd0 libctf0 \
# && apt -y autoremove \
# && apt install -y firefox-esr \ 
    && apt-get update --fix-missing \
    && apt install -y libgtk-3-0 iputils-ping sqlite3 sudo nano postgresql python3-psycopg2

# setup postgres db
RUN echo "local   all             all                                     trust" >> /etc/postgresql/13/main/pg_hba.conf \
    && echo "data_directory='/cinder/dqmsquare/pgdb'"  >>  /etc/postgresql/13/main/postgresql.conf
 
# ENV DEBIAN_FRONTEND noninteractive

# See Geckodriver & firefox compat here: https://firefox-source-docs.mozilla.org/testing/geckodriver/Support.html
ENV GECKODRIVER_VER v0.31.0
ENV FIREFOX_VER 91.2.0esr
# ENV BOTTLE_VER 0.12.19

# Add latest FireFox
RUN set -x \
  && apt install -y \
      libx11-xcb1 \
      libdbus-glib-1-2 \
  && curl -sSLO https://download-installer.cdn.mozilla.net/pub/firefox/releases/${FIREFOX_VER}/linux-x86_64/en-US/firefox-${FIREFOX_VER}.tar.bz2 \
  && tar -jxf firefox-* \
  && mv firefox /opt/ \
  && chmod 755 /opt/firefox \
  && chmod 755 /opt/firefox/firefox \ 
  # Add geckodriver
  && set -x \ 
  && curl -sSLO https://github.com/mozilla/geckodriver/releases/download/${GECKODRIVER_VER}/geckodriver-${GECKODRIVER_VER}-linux64.tar.gz \
  && tar zxf geckodriver-*.tar.gz \
  && mv geckodriver /usr/bin/

# RUN apt install -y libnss3-tools

RUN mkdir -p /cephfs/testbed/dqmsquare_mirror/

COPY . /dqmsquare_mirror
WORKDIR dqmsquare_mirror

RUN python3 -m pip install -U pip \
  && python3 -m pip install -r requirements \
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
RUN date

# add new user, add user to sudoers file, switch to user
RUN useradd dqm \
    && echo "%dqm ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers \
    && mkdir -p /home/dqm/ \
    && chmod 777 /home/dqm/ \
    && find /dqmsquare_mirror -type d -exec chmod 777 {} \; \ 
    && find /dqmsquare_mirror -type f -exec chmod 777 {} \; 
USER dqm
 
CMD ["/bin/bash"]





