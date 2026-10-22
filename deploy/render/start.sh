#!/usr/bin/env bash
# Render ishga tushirish: namoyish saytida demo ma'lumotlar bo'lmasa yaratiladi, so'ng gunicorn.
set -o errexit
if [ "${DEMO_SITE:-False}" = "True" ]; then
  python manage.py seed_demo --if-empty
fi
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-10000}" --workers "${WEB_CONCURRENCY:-2}" \
  --timeout 60 --access-logfile -
