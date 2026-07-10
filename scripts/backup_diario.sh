#!/bin/bash
export PGPASSWORD=sGXizxWs4khbF8ZJeOJ
BACKUP_DIR=/home/ibar/Proyectos/DepaFix/backups
mkdir -p $BACKUP_DIR
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
pg_dump -h localhost -U depafix -d depafix > $BACKUP_DIR/backup_$TIMESTAMP.sql
find $BACKUP_DIR -name "backup_*.sql" -mtime +7 -delete
echo "✅ Backup guardado: $BACKUP_DIR/backup_$TIMESTAMP.sql"
