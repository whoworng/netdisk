import os
import uuid
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    files = db.relationship("File", backref="owner", lazy="dynamic")
    folders = db.relationship("Folder", backref="owner", lazy="dynamic")
    activities = db.relationship("Activity", backref="user", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Folder(db.Model):
    __tablename__ = "folders"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("folders.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    children = db.relationship(
        "Folder", backref=db.backref("parent", remote_side="Folder.id"), lazy="dynamic"
    )
    files = db.relationship("File", backref="folder", lazy="dynamic")


class File(db.Model):
    __tablename__ = "files"

    id = db.Column(db.Integer, primary_key=True)
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), unique=True, nullable=False)
    size = db.Column(db.BigInteger, nullable=False)
    mime_type = db.Column(db.String(128), default="application/octet-stream")
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    folder_id = db.Column(db.Integer, db.ForeignKey("folders.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    shares = db.relationship("Share", backref="file", lazy="dynamic")

    @staticmethod
    def generate_stored_name(original_name):
        ext = os.path.splitext(original_name)[1]
        return f"{uuid.uuid4().hex}{ext}"


class Share(db.Model):
    __tablename__ = "shares"

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False)
    file_id = db.Column(db.Integer, db.ForeignKey("files.id"), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    download_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def generate_token():
        return uuid.uuid4().hex[:16]


class Activity(db.Model):
    __tablename__ = "activities"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action = db.Column(db.String(32), nullable=False)
    detail = db.Column(db.String(512), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
