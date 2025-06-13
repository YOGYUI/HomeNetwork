#!/bin/bash
curpath=$(dirname $(realpath $BASH_SOURCE))
/usr/bin/uwsgi ${curpath}/uwsgi.ini