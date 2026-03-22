import os
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask, request

from config import Config
from extensions import db, login_manager, init_redis
from models import User, File, Share


def setup_logging(app):
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)

    # 访问日志
    access_handler = RotatingFileHandler(
        os.path.join(log_dir, "access.log"),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
    )
    access_handler.setFormatter(
        logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    access_logger = logging.getLogger("access")
    access_logger.setLevel(logging.INFO)
    access_logger.addHandler(access_handler)

    # 错误日志
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

    # 请求结束后记录访问日志
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


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # 初始化日志
    setup_logging(app)

    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    init_redis(app)

    # 注册蓝图
    from auth import auth_bp
    from files import files_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(files_bp)

    # 创建数据库表
    with app.app_context():
        db.create_all()

    # 确保上传目录存在
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
