import os
import json
from datetime import datetime, timedelta, date

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
    jsonify,
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import func

from models import File, Share, Folder, Activity, format_size
from extensions import db, redis_client

files_bp = Blueprint("files", __name__)


def log_activity(action, detail=""):
    activity = Activity(
        user_id=current_user.id,
        action=action,
        detail=detail[:512],
    )
    db.session.add(activity)


def get_breadcrumbs(folder):
    crumbs = []
    current = folder
    while current:
        crumbs.append(current)
        current = current.parent
    crumbs.reverse()
    return crumbs


PREVIEWABLE_IMAGE = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml", "image/bmp"}
PREVIEWABLE_VIDEO = {"video/mp4", "video/webm", "video/ogg"}
PREVIEWABLE_AUDIO = {"audio/mpeg", "audio/ogg", "audio/wav", "audio/mp4", "audio/webm"}
PREVIEWABLE_TEXT = {
    "text/plain", "text/html", "text/css", "text/javascript",
    "application/json", "application/xml", "text/xml", "text/csv",
    "text/markdown", "application/x-yaml",
}


def get_preview_type(mime_type):
    if mime_type in PREVIEWABLE_IMAGE:
        return "image"
    if mime_type in PREVIEWABLE_VIDEO:
        return "video"
    if mime_type in PREVIEWABLE_AUDIO:
        return "audio"
    if mime_type in PREVIEWABLE_TEXT:
        return "text"
    if mime_type == "application/pdf":
        return "pdf"
    return None


@files_bp.route("/")
@login_required
def index():
    folder_id = request.args.get("folder_id", type=int)
    current_folder = None
    breadcrumbs = []

    if folder_id:
        current_folder = Folder.query.get_or_404(folder_id)
        if current_folder.user_id != current_user.id:
            abort(403)
        breadcrumbs = get_breadcrumbs(current_folder)

    folders = Folder.query.filter_by(
        user_id=current_user.id, parent_id=folder_id
    ).order_by(Folder.name).all()

    files = File.query.filter_by(
        user_id=current_user.id, folder_id=folder_id
    ).order_by(File.created_at.desc()).all()

    activities = Activity.query.filter_by(
        user_id=current_user.id
    ).order_by(Activity.created_at.desc()).limit(8).all()

    # 统计
    total_files = File.query.filter_by(user_id=current_user.id).count()
    total_size = db.session.query(
        func.coalesce(func.sum(File.size), 0)
    ).filter(File.user_id == current_user.id).scalar()
    total_shares = Share.query.join(File).filter(File.user_id == current_user.id).count()

    return render_template(
        "index.html",
        files=files,
        folders=folders,
        current_folder=current_folder,
        breadcrumbs=breadcrumbs,
        activities=activities,
        total_files=total_files,
        total_size=total_size,
        total_shares=total_shares,
        get_preview_type=get_preview_type,
    )


@files_bp.route("/upload", methods=["POST"])
@login_required
def upload():
    folder_id = request.form.get("folder_id", type=int)

    if folder_id:
        folder = Folder.query.get_or_404(folder_id)
        if folder.user_id != current_user.id:
            abort(403)

    uploaded = request.files.getlist("file")
    if not uploaded or all(f.filename == "" for f in uploaded):
        flash("没有选择文件", "error")
        return redirect(url_for("files.index", folder_id=folder_id))

    count = 0
    for f in uploaded:
        if f.filename == "":
            continue

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
            folder_id=folder_id,
        )
        db.session.add(file_record)
        count += 1

    if count > 0:
        log_activity("upload", f"上传了 {count} 个文件")
        db.session.commit()
        flash(f"成功上传 {count} 个文件", "success")
    else:
        flash("没有有效文件", "error")

    return redirect(url_for("files.index", folder_id=folder_id))


@files_bp.route("/upload/ajax", methods=["POST"])
@login_required
def upload_ajax():
    """AJAX 上传接口，支持拖拽上传"""
    folder_id = request.form.get("folder_id", type=int)

    if folder_id:
        folder = Folder.query.get_or_404(folder_id)
        if folder.user_id != current_user.id:
            return jsonify({"error": "无权限"}), 403

    uploaded = request.files.getlist("file")
    if not uploaded:
        return jsonify({"error": "没有文件"}), 400

    results = []
    for f in uploaded:
        if f.filename == "":
            continue

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
            folder_id=folder_id,
        )
        db.session.add(file_record)
        results.append({
            "name": original_name,
            "size": format_size(size),
        })

    if results:
        log_activity("upload", f"上传了 {len(results)} 个文件")
        db.session.commit()

    return jsonify({"uploaded": results, "count": len(results)})


@files_bp.route("/download/<int:file_id>")
@login_required
def download(file_id):
    file_record = File.query.get_or_404(file_id)
    if file_record.user_id != current_user.id:
        abort(403)

    log_activity("download", file_record.original_name)
    db.session.commit()

    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        file_record.stored_name,
        as_attachment=True,
        download_name=file_record.original_name,
    )


@files_bp.route("/preview/<int:file_id>")
@login_required
def preview(file_id):
    file_record = File.query.get_or_404(file_id)
    if file_record.user_id != current_user.id:
        abort(403)

    preview_type = get_preview_type(file_record.mime_type)
    if not preview_type:
        abort(415)

    if preview_type == "text":
        filepath = os.path.join(
            current_app.config["UPLOAD_FOLDER"], file_record.stored_name
        )
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(100 * 1024)  # max 100KB
        except Exception:
            content = "无法读取文件内容"
        return jsonify({"type": "text", "content": content, "name": file_record.original_name})

    # 图片/视频/音频/PDF 返回文件 URL
    return jsonify({
        "type": preview_type,
        "url": url_for("files.serve_file", file_id=file_id),
        "name": file_record.original_name,
    })


@files_bp.route("/file/<int:file_id>")
@login_required
def serve_file(file_id):
    file_record = File.query.get_or_404(file_id)
    if file_record.user_id != current_user.id:
        abort(403)

    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        file_record.stored_name,
        mimetype=file_record.mime_type,
    )


@files_bp.route("/delete/<int:file_id>", methods=["POST"])
@login_required
def delete(file_id):
    file_record = File.query.get_or_404(file_id)
    if file_record.user_id != current_user.id:
        abort(403)

    folder_id = file_record.folder_id

    filepath = os.path.join(
        current_app.config["UPLOAD_FOLDER"], file_record.stored_name
    )
    if os.path.exists(filepath):
        os.remove(filepath)

    Share.query.filter_by(file_id=file_record.id).delete()
    log_activity("delete", file_record.original_name)
    db.session.delete(file_record)
    db.session.commit()

    flash("文件已删除", "success")
    return redirect(url_for("files.index", folder_id=folder_id))


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
    log_activity("share", f"{file_record.original_name} ({hours}h)")
    db.session.commit()

    if redis_client:
        share_data = json.dumps({
            "file_id": file_record.id,
            "stored_name": file_record.stored_name,
            "original_name": file_record.original_name,
        })
        redis_client.setex(f"share:{token}", hours * 3600, share_data)

    share_url = url_for("files.shared_download", token=token, _external=True)
    flash(f"分享链接（{hours}小时有效）: {share_url}", "success")
    return redirect(url_for("files.index", folder_id=file_record.folder_id))


@files_bp.route("/s/<token>")
def shared_download(token):
    if redis_client:
        cached = redis_client.get(f"share:{token}")
        if cached:
            data = json.loads(cached)
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

    share = Share.query.filter_by(token=token).first_or_404()

    if share.expires_at and share.expires_at < datetime.utcnow():
        abort(410)

    share.download_count += 1
    db.session.commit()

    file_record = File.query.get_or_404(share.file_id)
    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        file_record.stored_name,
        as_attachment=True,
        download_name=file_record.original_name,
    )


# --- 文件夹相关路由 ---

@files_bp.route("/folder/create", methods=["POST"])
@login_required
def create_folder():
    name = request.form.get("name", "").strip()
    parent_id = request.form.get("parent_id", type=int)

    if not name:
        flash("文件夹名不能为空", "error")
        return redirect(url_for("files.index", folder_id=parent_id))

    if parent_id:
        parent = Folder.query.get_or_404(parent_id)
        if parent.user_id != current_user.id:
            abort(403)

    existing = Folder.query.filter_by(
        user_id=current_user.id, parent_id=parent_id, name=name
    ).first()
    if existing:
        flash("同名文件夹已存在", "error")
        return redirect(url_for("files.index", folder_id=parent_id))

    folder = Folder(name=name, parent_id=parent_id, user_id=current_user.id)
    db.session.add(folder)
    log_activity("create_folder", name)
    db.session.commit()

    flash(f"文件夹 \"{name}\" 已创建", "success")
    return redirect(url_for("files.index", folder_id=parent_id))


@files_bp.route("/folder/<int:folder_id>/rename", methods=["POST"])
@login_required
def rename_folder(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    if folder.user_id != current_user.id:
        abort(403)

    new_name = request.form.get("name", "").strip()
    if not new_name:
        flash("名称不能为空", "error")
        return redirect(url_for("files.index", folder_id=folder.parent_id))

    old_name = folder.name
    folder.name = new_name
    log_activity("rename_folder", f"{old_name} -> {new_name}")
    db.session.commit()

    flash(f"已重命名为 \"{new_name}\"", "success")
    return redirect(url_for("files.index", folder_id=folder.parent_id))


@files_bp.route("/folder/<int:folder_id>/delete", methods=["POST"])
@login_required
def delete_folder(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    if folder.user_id != current_user.id:
        abort(403)

    parent_id = folder.parent_id
    _delete_folder_recursive(folder)
    log_activity("delete_folder", folder.name)
    db.session.commit()

    flash(f"文件夹 \"{folder.name}\" 已删除", "success")
    return redirect(url_for("files.index", folder_id=parent_id))


def _delete_folder_recursive(folder):
    for child in folder.children.all():
        _delete_folder_recursive(child)

    for f in folder.files.all():
        filepath = os.path.join(
            current_app.config["UPLOAD_FOLDER"], f.stored_name
        )
        if os.path.exists(filepath):
            os.remove(filepath)
        Share.query.filter_by(file_id=f.id).delete()
        db.session.delete(f)

    db.session.delete(folder)
