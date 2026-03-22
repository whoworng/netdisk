import os

from flask import Flask

from config import Config
from extensions import db, login_manager, init_redis
from models import User, File, Share


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

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
