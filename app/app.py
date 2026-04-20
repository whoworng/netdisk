import os
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask, request
from sqlalchemy import text

from config import Config
from extensions import db, login_manager, init_redis
from models import User, File, Share, Folder, Activity, format_size


def setup_logging(app):
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)

    access_handler = RotatingFileHandler(
        os.path.join(log_dir, "access.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    access_handler.setFormatter(
        logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    access_logger = logging.getLogger("access")
    access_logger.setLevel(logging.INFO)
    access_logger.addHandler(access_handler)

    error_handler = RotatingFileHandler(
        os.path.join(log_dir, "error.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    error_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    app.logger.addHandler(error_handler)
    app.logger.setLevel(logging.INFO)

    @app.after_request
    def log_request(response):
        access_logger.info(
            '%s %s %s %s %s',
            request.remote_addr,
            request.method,
            request.path,
            response.status_code,
            response.content_length or 0,
        )
        return response


def migrate_db(app):
    """兼容迁移：给 files 表添加 folder_id 列（如果不存在）"""
    with app.app_context():
        try:
            result = db.session.execute(
                text("SHOW COLUMNS FROM files LIKE 'folder_id'")
            )
            if result.rowcount == 0:
                db.session.execute(
                    text("ALTER TABLE files ADD COLUMN folder_id INTEGER NULL")
                )
                db.session.execute(
                    text(
                        "ALTER TABLE files ADD CONSTRAINT fk_files_folder_id "
                        "FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL"
                    )
                )
                db.session.commit()
                app.logger.info("Migration: added folder_id column to files table")
        except Exception as e:
            db.session.rollback()
            app.logger.warning(f"Migration check skipped: {e}")


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    setup_logging(app)

    db.init_app(app)
    login_manager.init_app(app)
    init_redis(app)

    # 注册 Jinja2 过滤器
    app.jinja_env.filters["format_size"] = format_size

    from auth import auth_bp
    from files import files_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(files_bp)

    with app.app_context():
        db.create_all()

    migrate_db(app)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
