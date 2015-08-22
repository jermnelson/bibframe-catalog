#!/bin/bash
set -e

exec nohup uwsgi -s /tmp/bibcat.sock -w runserver:app --chmod-socket=666 &
exec gosu service nginx start
