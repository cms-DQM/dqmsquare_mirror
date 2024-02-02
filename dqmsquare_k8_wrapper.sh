#!/bin/bash

# Wrapper script for launching the Mirror on a kubernetes pod. 
# Accepts one argument, the type of service to run. Can be "server", "dummy".
# Launches two python grabbers in the background, and then runs the flash app with
# gunicorn.

service=$1

LOGS_DIR=/cinder/dqmsquare/log/
PVC_DIR=/cinder/dqmsquare

echo Creating logs dir $LOGS_DIR ...
sudo mkdir -p $LOGS_DIR

echo Changing permissions for PVC claim $PVC_DIR ...
sudo find  -type d -exec chmod 777 {} \;


python3 dqmsquare_cfg.py k8

if [[ $service ]] && [[ $service = "server" ]] ; then
  python3 grabber.py production & 
  python3 grabber.py playback & 

  # Launch gunicorn with 4 workers.
  gunicorn -w 4 -b 0.0.0.0:8084 'wsgi:flask_app'
fi

if [[ $service ]] && [[ $service = "dummy" ]] ; then
  while true; do
	  echo "Sleeping ..."
	  sleep 60
  done
fi