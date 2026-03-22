import os
import json
from datetime import datetime, timedelta

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    send_from_directory,
    current_app,
    abort,
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from models import File, Share
from extensions import db, redis_client

files_bp = Blueprint("files", __name__)


@files_bp.route("/")
@login_required
def index():
    user_files = current_user.files.order_by(File.created_at.desc()).all()
    return render_template("index.html", files=user_files)


@files_bp.route("/upload", methods=["POST"])
@login_required
def upload():
    if "file" not in request.files:
        flash("没有选择文件", "error")
        return redirect(url_for("files.index"))

    f = request.files["file"]
    if f.filename == "":
        flash("没有选择文件", "error")
        return redirect(url_for("files.index"))

    original_name = secure_filename(f.filename)
    if not original_name:
        original_name = "unnamed_file"

    stored_name = File.generate_stored_name(original_name)
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)

    filepath = os.path.join(upload_folder, stored_name)
    f.save(filepath)

    size = os.path.getsize(filepath)
    mime_type = f.content_type or "application/octet-stream"

    file_record = File(
        original_name=original_name,
        stored_name=stored_name,
        size=size,
        mime_type=mime_type,
        user_id=current_user.id,
    )
    db.session.add(file_record)
    db.session.commit()

    flash(f"上传成功: {original_name}", "success")
    return redirect(url_for("files.index"))


@files_bp.route("/download/<int:file_id>")
@login_required
def download(file_id):
    file_record = File.query.get_or_404(file_id)
    if file_record.user_id != current_user.id:
        abort(403)

    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        file_record.stored_name,
        as_attachment=True,
        download_name=file_record.original_name,
    )


@files_bp.route("/delete/<int:file_id>", methods=["POST"])
@login_required
def delete(file_id):
    file_record = File.query.get_or_404(file_id)
    if file_record.user_id != current_user.id:
        abort(403)

    # 删除磁盘文件
    filepath = os.path.join(
        current_app.config["UPLOAD_FOLDER"], file_record.stored_name
    )
    if os.path.exists(filepath):
        os.remove(filepath)

    # 删除关联的分享记录
    Share.query.filter_by(file_id=file_record.id).delete()

    db.session.delete(file_record)
    db.session.commit()

    flash("文件已删除", "success")
    return redirect(url_for("files.index"))


@files_bp.route("/share/<int:file_id>", methods=["POST"])
@login_required
def create_share(file_id):
    file_record = File.query.get_or_404(file_id)
    if file_record.user_id != current_user.id:
        abort(403)

    hours = int(request.form.get("hours", 24))
    token = Share.generate_token()
    expires_at = datetime.utcnow() + timedelta(hours=hours)

    share = Share(token=token, file_id=file_record.id, expires_at=expires_at)
    db.session.add(share)
    db.session.commit()

    # 缓存分享信息到 Redis
    if redis_client:
        share_data = json.dumps(
            {
                "file_id": file_record.id,
                "stored_name": file_record.stored_name,
                "original_name": file_record.original_name,
            }
        )
        redis_client.setex(f"share:{token}", hours * 3600, share_data)

    share_url = url_for("files.shared_download", token=token, _external=True)
    flash(f"分享链接（{hours}小时有效）: {share_url}", "success")
    return redirect(url_for("files.index"))


@files_bp.route("/s/<token>")
def shared_download(token):
    # 先查 Redis 缓存
    if redis_client:
        cached = redis_client.get(f"share:{token}")
        if cached:
            data = json.loads(cached)
            # 更新数据库下载计数
            share = Share.query.filter_by(token=token).first()
            if share:
                share.download_count += 1
                db.session.commit()

            return send_from_directory(
                current_app.config["UPLOAD_FOLDER"],
                data["stored_name"],
                as_attachment=True,
                download_name=data["original_name"],
            )

    # Redis 没有则查数据库
    share = Share.query.filter_by(token=token).first_or_404()

    if share.expires_at and share.expires_at < datetime.utcnow():
        abort(410)  # Gone - 链接已过期

    share.download_count += 1
    db.session.commit()

    file_record = File.query.get_or_404(share.file_id)
    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        file_record.stored_name,
        as_attachment=True,
        download_name=file_record.original_name,
    )
