#!/bin/bash
exec nohup uwsgi -s /tmp/bibcat.sock -w runserver:app --chmod-socket=666 &
exec nginx -g 'daemon off;'
