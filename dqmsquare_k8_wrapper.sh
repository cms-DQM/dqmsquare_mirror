#!/bin/bash

service=$1

#sudo mkdir -p /cephfs/testbed/dqmsquare_mirror/db/
#sudo mkdir -p /cephfs/testbed/dqmsquare_mirror/tmp/
#sudo mkdir -p /cephfs/testbed/dqmsquare_mirror/log/
#sudo find /cephfs/testbed/dqmsquare_mirror -type d -exec chmod 777 {} \;

sudo mkdir -p /cinder/dqmsquare/db/
sudo mkdir -p /cinder/dqmsquare/tmp/
sudo mkdir -p /cinder/dqmsquare/log/
sudo find /cinder/dqmsquare -type d -exec chmod 777 {} \;
sudo chown postgres:postgres /cinder/dqmsquare/db

/usr/lib/postgresql/13/bin/pg_ctl -D /cinder/dqmsquare/pgdb initdb
sudo chown -R postgres /cinder/dqmsquare/pgdb
sudo find /cinder/dqmsquare/pgdb -type d -exec chmod 0700 {} \;

python3 dqmsquare_cfg.py k8

if [ $service = "server" ] ; then
  # python3 dqmsquare_server.py
  sudo service postgresql start
  gunicorn -w 4 -b 0.0.0.0:8084 'dqmsquare_server_flask:gunicorn_app'

  # python3 dqmsquare_grabber.py production
  # python3 dqmsquare_grabber.py playback
fi

if [ $service = "dummy" ] ; then
  while true; do
	  echo "Sleep ..."
	  sleep 60
  done
fi



