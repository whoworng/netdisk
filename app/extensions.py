from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import redis as redis_lib

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"

redis_client = None


def init_redis(app):
    global redis_client
    redis_client = redis_lib.Redis(
        host=app.config["REDIS_HOST"],
        port=app.config["REDIS_PORT"],
        db=app.config["REDIS_DB"],
        decode_responses=True,
    )
