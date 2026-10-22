#!/usr/bin/env bash
# Render build bosqichi: paketlar, statik fayllar, baza migratsiyalari.
set -o errexit
pip install --upgrade pip
pip install -r requirements.lock
python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py createcachetable
