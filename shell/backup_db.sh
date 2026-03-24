#!/bin/bash

SH_DATE=$(date +%F)
USER=netdisk
PASSWORD=netdisk123
DB_NAME=netdisk
BACKUP_DIR=/tmp/backup/

if ! [ -d "$BACKUP_DIR" ]; then
  mkdir -p "$BACKUP_DIR"
fi

mysqldump --no-tablespaces -u "$USER" -p"$PASSWORD" "$DB_NAME" >"$BACKUP_DIR"backup_"$SH_DATE".sql 2>/dev/null

if [ $? -eq 0 ]; then
  echo "[$(date)] 数据库备份成功"
else
  echo "[$(date)] 备份失败"
fi

echo "三秒后开始清理7天前的文件"
sleep 3
find "$BACKUP_DIR" -name "*.sql" -mtime +7 -delete

exit 0
