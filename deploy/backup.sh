#!/usr/bin/env bash
# Baza va maxfiy hujjatlarning kunlik zaxirasi. Ishlatish: deploy/backup.sh  (cron: deploy/cron-socialpuls)
set -euo pipefail
APP_DIR="${APP_DIR:-/srv/socialpuls}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/socialpuls}"
KEEP_DAYS="${KEEP_DAYS:-14}"

# .env bash orqali "source" qilinmaydi (qiymatlarda bo'shliq va < > bo'lishi mumkin), faqat kerakli kalitlar o'qiladi.
env_get() { grep -E "^$1=" "$APP_DIR/.env" | tail -1 | cut -d= -f2-; }
DATABASE_URL="$(env_get DATABASE_URL)"
PRIVATE_MEDIA_ROOT="$(env_get PRIVATE_MEDIA_ROOT)"
: "${DATABASE_URL:?.env da DATABASE_URL yo'q}" "${PRIVATE_MEDIA_ROOT:?.env da PRIVATE_MEDIA_ROOT yo'q}"
stamp="$(date +%Y%m%d-%H%M)"
mkdir -p "$BACKUP_DIR"
umask 077

pg_dump --format=custom --no-owner --dbname="$DATABASE_URL" --file="$BACKUP_DIR/db-$stamp.dump"
tar -czf "$BACKUP_DIR/files-$stamp.tar.gz" -C "$(dirname "$PRIVATE_MEDIA_ROOT")" "$(basename "$PRIVATE_MEDIA_ROOT")"

find "$BACKUP_DIR" -type f \( -name 'db-*.dump' -o -name 'files-*.tar.gz' \) -mtime +"$KEEP_DAYS" -delete
echo "$(date '+%F %T') zaxira tayyor: $stamp"
