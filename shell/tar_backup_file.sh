#!/bin/bash

SQL_BACKUP_DIR=/tmp/backup/
TAR_BACKUP_DIR=/home/liujixiang/devops/project/backup/
NOW_DATE=$(date +%F)

if ! [ -d "$TAR_BACKUP_DIR" ]; then
  echo "不存在目录$TAR_BACKUP_DIR,请检查"
  exit 1
fi

if find "$SQL_BACKUP_DIR" -type f -name "*.sql" | grep -q .; then
  find "$SQL_BACKUP_DIR" -type f -name "*.sql" -mtime -3 | tar cf "$TAR_BACKUP_DIR"/"$NOW_DATE".bak -T -
else
  echo "${SQL_BACKUP_DIR}下无可备份的SQL文件"
fi

exit 0
