#!/usr/bin/env bash
# Backup MySQL hằng ngày với retention (spec production-hardening 15-08-2026).
# Chạy trong container mysql:8 (có sẵn mysqldump). ONE_SHOT=1 để chạy một vòng
# rồi thoát (dùng cho kiểm thử/diễn tập restore).
set -euo pipefail

RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
INTERVAL_SECONDS="${BACKUP_INTERVAL_SECONDS:-86400}"

backup_once() {
    local stamp file
    stamp="$(date +%Y%m%d-%H%M%S)"
    file="/backups/${MYSQL_DATABASE}-${stamp}.sql.gz"
    echo "[backup] dumping ${MYSQL_DATABASE} -> ${file}"
    mysqldump \
        --host="${MYSQL_HOST}" \
        --user="${MYSQL_USER}" \
        --password="${MYSQL_PASSWORD}" \
        --single-transaction \
        --routines \
        --triggers \
        "${MYSQL_DATABASE}" | gzip > "${file}"
    echo "[backup] done: $(du -h "${file}" | cut -f1)"

    echo "[backup] pruning older than ${RETENTION_DAYS} days"
    find /backups -name "${MYSQL_DATABASE}-*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete
}

if [ "${ONE_SHOT:-0}" = "1" ]; then
    backup_once
    exit 0
fi

while true; do
    backup_once || echo "[backup] FAILED — thử lại ở vòng sau"
    sleep "${INTERVAL_SECONDS}"
done
