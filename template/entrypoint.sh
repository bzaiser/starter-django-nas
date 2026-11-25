#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py domain_ctl --seed-defaults 2>/dev/null || true
python manage.py ops_auto_update --startup 2>/dev/null || true
python manage.py shell -c "import os; from django.contrib.auth import get_user_model; U=get_user_model(); u=os.environ.get('DJANGO_ADMIN_USER','admin'); e=os.environ.get('DJANGO_ADMIN_EMAIL','admin@localhost'); p=os.environ.get('DJANGO_ADMIN_PASSWORD','admin'); U.objects.filter(username=u).exists() or U.objects.create_superuser(u,e,p)"

exec ${START_COMMAND:-gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --threads 4}
