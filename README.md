# NetDisk

一个简单的网盘项目，用于学习devops技术。从本机部署到 Docker 容器化，逐步实践完整的运维技术栈。

## 技术栈

| 类别 | 技术 |
|------|------|
| 基础 | Linux、Nginx、MySQL、Redis、Shell、Git |
| 容器 | Docker |
| 监控 | Prometheus、Grafana、ELK、Alertmanager |

## 项目架构

```
用户浏览器
    │
    ▼
  Nginx（反向代理 + 静态资源）
    │
    ▼
  Flask 应用（Python）
    ├── MySQL（用户数据、文件元数据）
    └── Redis（会话缓存、分享链接）
```

## 目录结构

```
.
├── app/                  # Flask 应用代码
│   ├── app.py            # 入口文件
│   ├── config.py         # 配置
│   ├── models.py         # 数据模型
│   ├── auth.py           # 用户认证
│   ├── files.py          # 文件管理
│   ├── templates/        # 前端模板
│   ├── static/           # 静态资源
│   └── logs/             # 应用日志
├── nginx/                # Nginx 配置
├── shell/                # 运维脚本
│   ├── backup_db.sh      # 数据库备份
│   └── tar_backup_file.sh # 文件备份
├── backup/               # 备份存放
│   ├── database/
│   └── file/
└── media/                # 用户上传文件
    └── uploads/
```

## 注意
拉镜像超时可以修改Dockerfile第4行为指定国内镜像源
```
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

需要加入你自己的app/.env使用
模板：
```
DB_HOST=database
DB_PORT=3306
DB_NAME=netdisk

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# 应用
SECRET_KEY=change-me-to-a-random-string
UPLOAD_FOLDER=/app/uploads
```

## 版本

- **v1.0** - 本机部署版本（Nginx + Flask + MySQL + Redis + systemd）
- **v2.0** - Docker 容器化版本
