#!/bin/bash

service=$1

#sudo mkdir -p /cephfs/testbed/dqmsquare_mirror/db/
#sudo mkdir -p /cephfs/testbed/dqmsquare_mirror/tmp/
#sudo mkdir -p /cephfs/testbed/dqmsquare_mirror/log/
#sudo find /cephfs/testbed/dqmsquare_mirror -type d -exec chmod 777 {} \;

sudo mkdir -p /cinder/dqmsquare/log/
sudo find /cinder/dqmsquare -type d -exec chmod 777 {} \;

python3 dqmsquare_cfg.py k8

if [[ $service ]] && [[ $service = "server" ]] ; then
  # python3 dqmsquare_server.py
  sudo service postgresql start
  # DB 'postgres' is created by default, create  'postgres_production' database too
  sudo -u dqm createdb postgres_production 
  python3 grabber.py production & 
  python3 grabber.py playback & 

  gunicorn -w 4 -b 0.0.0.0:8084 'wsgi:flask_app'
fi

if [[ $service ]] && [[ $service = "dummy" ]] ; then
  while true; do
	  echo "Sleep ..."
	  sleep 60
  done
fi