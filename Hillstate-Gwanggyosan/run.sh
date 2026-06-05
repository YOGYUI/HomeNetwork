#!/bin/bash
curpath=$(dirname $(realpath $BASH_SOURCE))
/usr/bin/uwsgi ${curpath}/uwsgi.ini \
  --pyargv "--config_file_path=$ \
  --mqtt_broker= \
  --rs485= \
  --discovery= \
  --parser_mapping= \
  --periodic_query_state= \
  --subphone= \
  --etc= \
  --debug= \
  "