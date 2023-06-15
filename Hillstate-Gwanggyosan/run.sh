#! /usr/sh
curpath=$(dirname $(realpath $BASH_SOURCE))
/usr/local/bin/uwsgi ${curpath}/uwsgi.ini