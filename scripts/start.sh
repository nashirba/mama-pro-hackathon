#!/bin/sh
set -e
python manage.py migrate --noinput
python manage.py seed_demo
exec gunicorn config.wsgi --bind 0.0.0.0:$PORT --workers 2
