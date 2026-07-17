#!/bin/bash
FECHA=$(date +%Y%m%d_%H%M)
DIR="/tmp/depafix_backups"
mkdir -p $DIR
: "${PGPASSWORD:?Falta PGPASSWORD en el entorno (credencial hardcodeada removida, auditoria 2026-07-16 -- repo publico)}"
LOG="/home/ibar/Proyectos/DepaFix/core/logs/backup_cloud.log"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Iniciando backup $FECHA" >> "$LOG"
pg_dump -h localhost -U depafix depafix -Fc > "$DIR/depafix_$FECHA.dump" && \
gzip "$DIR/depafix_$FECHA.dump" && \
echo "[OK] Backup local: $DIR/depafix_$FECHA.dump.gz" >> "$LOG"
if command -v rclone &>/dev/null; then
    rclone copy "$DIR/depafix_$FECHA.dump.gz" "b2:depafix-backups/" 2>>$LOG && \
    echo "[OK] Subido a Backblaze B2" >> "$LOG"
    find $DIR -name "*.gz" -mtime +7 -delete
else
    echo "[WARN] rclone no instalado. Backup solo local." >> "$LOG"
fi
ls -lh $DIR/*.gz 2>/dev/null | tail -3
