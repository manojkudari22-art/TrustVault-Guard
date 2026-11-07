import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, request, redirect, url_for, flash, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app import db
from app.documents.models import Document
from app.auth.models import User
from app.documents.permissions import DocumentPermission
from app.audit.utils import log_audit_event

documents = Blueprint("documents", __name__, url_prefix="/documents")

ALLOWED_EXTENSIONS = {
    "pdf": {"application/pdf"},
    "txt": {"text/plain"},
    "png": {"image/png"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "doc": {"application/msword"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    },
}


def allowed_file(filename, mimetype):
    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()

    return (
        extension in ALLOWED_EXTENSIONS
        and mimetype in ALLOWED_EXTENSIONS[extension]
    )


@documents.route("/upload", methods=["POST"])
@login_required
def upload_document():

    if current_user.role not in ["Document Owner", "Administrator"]:
        flash("You are not authorized to upload documents.", "error")
        return redirect(url_for("auth.dashboard"))

    uploaded_file = request.files.get("file")

    if not uploaded_file or not uploaded_file.filename:
        flash("Please select a file.", "error")
        return redirect(url_for("auth.dashboard"))

    original_filename = secure_filename(uploaded_file.filename)

    if not original_filename:
        flash("Invalid filename.", "error")
        return redirect(url_for("auth.dashboard"))

    if not allowed_file(original_filename, uploaded_file.mimetype):
        flash("File type is not allowed.", "error")
        return redirect(url_for("auth.dashboard"))

    extension = original_filename.rsplit(".", 1)[1].lower()
    stored_filename = f"{uuid.uuid4().hex}.{extension}"

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    upload_folder.mkdir(parents=True, exist_ok=True)

    file_path = upload_folder / stored_filename
    uploaded_file.save(file_path)

    document = Document(
        name=original_filename,
        original_filename=original_filename,
        stored_filename=stored_filename,
        category=request.form.get("category", "General"),
        owner_id=current_user.id,
    )

    try:
        db.session.add(document)
        db.session.commit()

        log_audit_event(
            user_id=current_user.id,
            document_id=document.id,
            action="DOCUMENT_UPLOAD",
            details=f"Uploaded document: {original_filename}",
        )

    except Exception:
        db.session.rollback()
        file_path.unlink(missing_ok=True)
        raise

    flash("Document uploaded successfully.", "success")
    return redirect(url_for("auth.dashboard"))
from flask import render_template

@documents.route("/my-documents")
@login_required
def my_documents():
    if current_user.role not in ["Document Owner", "Administrator"]:
        flash("You are not authorized to view these documents.", "error")
        return redirect(url_for("auth.dashboard"))

    query = Document.query.filter_by(owner_id=current_user.id, deleted_at=None)

    search = request.args.get("q", "").strip()[:100]
    category = request.args.get("category", "").strip()[:100]
    date_filter = request.args.get("date", "").strip()

    if search:
        query = query.filter(Document.name.ilike(f"%{search}%"))

    if category:
        query = query.filter_by(category=category)

    if date_filter:
        try:
            selected_date = datetime.strptime(date_filter, "%Y-%m-%d")
        except ValueError:
            from flask import abort
            abort(400)

        next_date = selected_date + timedelta(days=1)
        query = query.filter(
            Document.uploaded_at >= selected_date,
            Document.uploaded_at < next_date
        )

    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        from flask import abort
        abort(400)

    if page < 1:
        from flask import abort
        abort(400)

    per_page = 10
    total_documents = query.count()
    total_pages = max(1, (total_documents + per_page - 1) // per_page)
    page = min(page, total_pages)

    documents_page = (
        query.order_by(Document.uploaded_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    categories = [
        row[0] for row in
        db.session.query(Document.category)
        .filter_by(owner_id=current_user.id)
        .distinct()
        .order_by(Document.category)
        .all()
    ]

    return render_template(
        "documents/list.html",
        documents=documents_page,
        search=search,
        category=category,
        date_filter=date_filter,
        categories=categories,
        page=page,
        total_pages=total_pages,
        total_documents=total_documents
    )
@documents.route("/download/<int:document_id>")
@login_required
def download_document(document_id):
    document = db.session.get(Document, document_id)

    if document is None or document.deleted_at is not None:
        flash("Document not found.", "error")
        return redirect(url_for("auth.dashboard"))

    is_owner = document.owner_id == current_user.id

    permission = None
    if not is_owner:
        permission = DocumentPermission.query.filter_by(
            document_id=document.id,
            user_id=current_user.id,
            is_active=True
        ).first()

    has_download_access = (
        is_owner or
        (
            permission is not None and
            permission.permission in {"download", "edit"}
        )
    )

    if not has_download_access:
        log_audit_event(
            user_id=current_user.id,
            document_id=document.id,
            action="ACCESS_DENIED",
            details="Unauthorized document download attempt"
        )

        flash("You are not authorized to download this document.", "error")
        return redirect(url_for("auth.dashboard"))

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])

    log_audit_event(
        user_id=current_user.id,
        document_id=document.id,
        action="DOCUMENT_DOWNLOAD",
        details="Document downloaded successfully"
    )

    return send_from_directory(
        upload_folder,
        document.stored_filename,
        as_attachment=True,
        download_name=document.original_filename
    )
@documents.route("/view/<int:document_id>")
@login_required
def view_document(document_id):
    document = db.session.get(Document, document_id)

    if document is None or document.deleted_at is not None:
        from flask import abort
        abort(404)

    is_owner = document.owner_id == current_user.id

    permission = None
    if not is_owner:
        permission = DocumentPermission.query.filter_by(
            document_id=document.id,
            user_id=current_user.id,
            is_active=True
        ).first()

    has_view_access = (
        is_owner or (
            permission is not None and
            permission.permission in {"view", "download", "edit"}
        )
    )

    if not has_view_access:
        log_audit_event(
            user_id=current_user.id,
            document_id=document.id,
            action="ACCESS_DENIED",
            details="Unauthorized document preview attempt"
        )
        flash("You are not authorized to view this document.", "error")
        return redirect(url_for("auth.dashboard"))

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])

    log_audit_event(
        user_id=current_user.id,
        document_id=document.id,
        action="DOCUMENT_VIEW",
        details="Document preview accessed successfully"
    )

    response = send_from_directory(
        upload_folder,
        document.stored_filename,
        as_attachment=False,
        download_name=document.original_filename
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@documents.route("/upload", methods=["GET"])
@login_required
def upload_page():
    if current_user.role not in ["Document Owner", "Administrator"]:
        flash("You are not authorized to upload documents.", "error")
        return redirect(url_for("auth.dashboard"))

    return render_template("documents/upload.html")




@documents.route("/share/<int:document_id>", methods=["POST"])
@login_required
def share_document(document_id):
    document = db.session.get(Document, document_id)

    if document is None or document.deleted_at is not None or document.owner_id != current_user.id:
        flash("You are not authorized to share this document.", "error")
        return redirect(url_for("documents.my_documents"))

    username = request.form.get("username", "").strip()
    permission_level = request.form.get("permission", "").strip().lower()

    if permission_level not in {"view", "download", "edit"}:
        flash("Invalid permission selected.", "error")
        return redirect(url_for("documents.my_documents"))

    recipient = User.query.filter_by(
        username=username,
        is_active=True
    ).first()

    if recipient is None or recipient.id == current_user.id:
        flash("Please enter a valid recipient username.", "error")
        return redirect(url_for("documents.my_documents"))

    try:
        existing = DocumentPermission.query.filter_by(
            document_id=document.id,
            user_id=recipient.id
        ).first()

        if existing:
            existing.permission = permission_level
            existing.granted_by = current_user.id
            existing.is_active = True
            existing.revoked_at = None
        else:
            db.session.add(DocumentPermission(
                document_id=document.id,
                user_id=recipient.id,
                permission=permission_level,
                granted_by=current_user.id,
                is_active=True
            ))

        log_audit_event(
            user_id=current_user.id,
            document_id=document.id,
            action="PERMISSION_GRANTED",
            details=f"Granted {permission_level} permission to user ID {recipient.id}"
        )

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Document sharing failed")
        flash("Unable to share document.", "error")
        return redirect(url_for("documents.my_documents"))

    flash("Document shared successfully.", "success")
    return redirect(url_for("documents.my_documents"))


@documents.route("/revoke/<int:document_id>/<int:user_id>", methods=["POST"])
@login_required
def revoke_document_access(document_id, user_id):
    document = db.session.get(Document, document_id)

    if document is None or document.deleted_at is not None or document.owner_id != current_user.id:
        flash("You are not authorized to revoke access.", "error")
        return redirect(url_for("documents.my_documents"))

    permission = DocumentPermission.query.filter_by(
        document_id=document.id,
        user_id=user_id,
        is_active=True
    ).first()

    if permission is None:
        flash("Active permission not found.", "error")
        return redirect(url_for("documents.my_documents"))

    try:
        permission.is_active = False
        permission.revoked_at = datetime.now(timezone.utc)

        log_audit_event(
            user_id=current_user.id,
            document_id=document.id,
            action="PERMISSION_REVOKED",
            details=f"Revoked access for user ID {user_id}"
        )

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Permission revocation failed")
        flash("Unable to revoke access.", "error")
        return redirect(url_for("documents.my_documents"))

    flash("Document access revoked successfully.", "success")
    return redirect(url_for("documents.my_documents"))

@documents.route("/shared-with-me")
@login_required
def shared_with_me():
    query = (
        Document.query
        .join(
            DocumentPermission,
            DocumentPermission.document_id == Document.id
        )
        .filter(
            Document.deleted_at.is_(None),
            DocumentPermission.user_id == current_user.id,
            DocumentPermission.is_active.is_(True)
        )
    )

    search = request.args.get("q", "").strip()[:100]
    category = request.args.get("category", "").strip()[:100]
    date_filter = request.args.get("date", "").strip()

    if search:
        query = query.filter(Document.name.ilike(f"%{search}%"))

    if category:
        query = query.filter(Document.category == category)

    if date_filter:
        try:
            selected_date = datetime.strptime(date_filter, "%Y-%m-%d")
        except ValueError:
            from flask import abort
            abort(400)

        next_date = selected_date + timedelta(days=1)
        query = query.filter(
            Document.uploaded_at >= selected_date,
            Document.uploaded_at < next_date
        )

    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        from flask import abort
        abort(400)

    if page < 1:
        from flask import abort
        abort(400)

    per_page = 10
    total_documents = query.count()
    total_pages = max(1, (total_documents + per_page - 1) // per_page)
    page = min(page, total_pages)

    documents_page = (
        query.order_by(Document.uploaded_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    for document in documents_page:
        permission = DocumentPermission.query.filter_by(
            document_id=document.id,
            user_id=current_user.id,
            is_active=True
        ).first()
        document.current_permission = permission.permission

    categories = [
        row[0] for row in
        db.session.query(Document.category)
        .join(
            DocumentPermission,
            DocumentPermission.document_id == Document.id
        )
        .filter(
            Document.deleted_at.is_(None),
            DocumentPermission.user_id == current_user.id,
            DocumentPermission.is_active.is_(True)
        )
        .distinct()
        .order_by(Document.category)
        .all()
    ]

    return render_template(
        "documents/list.html",
        documents=documents_page,
        search=search,
        category=category,
        date_filter=date_filter,
        categories=categories,
        page=page,
        total_pages=total_pages,
        total_documents=total_documents,
        shared_mode=True
    )
@documents.route("/edit/<int:document_id>", methods=["POST"])
@login_required
def edit_document(document_id):
    document = db.session.get(Document, document_id)

    if document is None or document.deleted_at is not None:
        flash("Document not found.", "error")
        return redirect(url_for("documents.my_documents"))

    if document.owner_id != current_user.id:
        log_audit_event(
            user_id=current_user.id,
            document_id=document.id,
            action="ACCESS_DENIED",
            details="Unauthorized document edit attempt"
        )
        flash("Only the document owner can edit it.", "error")
        return redirect(url_for("documents.my_documents"))

    name = request.form.get("name", "").strip()[:255]
    category = request.form.get("category", "").strip()[:100]

    if not name or not category:
        flash("Name and category are required.", "error")
        return redirect(url_for("documents.my_documents"))

    old_name = document.name
    old_category = document.category

    try:
        document.name = name
        document.category = category

        log_audit_event(
            user_id=current_user.id,
            document_id=document.id,
            action="DOCUMENT_EDIT",
            details=(
                f"Updated document metadata. "
                f"Name: {old_name} -> {name}; "
                f"Category: {old_category} -> {category}"
            )
        )

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Document edit failed")
        flash("Unable to edit document.", "error")
        return redirect(url_for("documents.my_documents"))

    flash("Document updated successfully.", "success")
    return redirect(url_for("documents.my_documents"))


@documents.route("/delete/<int:document_id>", methods=["POST"])
@login_required
def delete_document(document_id):
    document = db.session.get(Document, document_id)

    if document is None or document.deleted_at is not None:
        flash("Document not found.", "error")
        return redirect(url_for("documents.my_documents"))

    if document.owner_id != current_user.id:
        log_audit_event(
            user_id=current_user.id,
            document_id=document.id,
            action="ACCESS_DENIED",
            details="Unauthorized document deletion attempt"
        )
        flash("Only the document owner can delete it.", "error")
        return redirect(url_for("documents.my_documents"))

    file_path = Path(current_app.config["UPLOAD_FOLDER"]) / document.stored_filename

    try:
        document.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)

        active_permissions = DocumentPermission.query.filter_by(
            document_id=document.id,
            is_active=True
        ).all()

        revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)

        for permission in active_permissions:
            permission.is_active = False
            permission.revoked_at = revoked_at

        log_audit_event(
            user_id=current_user.id,
            document_id=document.id,
            action="DOCUMENT_DELETE",
            details=f"Soft-deleted document ID {document.id}: {document.name}"
        )

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Document deletion transaction failed")
        flash("Unable to delete document.", "error")
        return redirect(url_for("documents.my_documents"))

    try:
        if file_path.exists():
            file_path.unlink()
    except OSError:
        current_app.logger.exception(
            "Physical file cleanup failed for deleted document ID %s",
            document.id
        )
        flash(
            "Document access was deleted, but physical file cleanup needs attention.",
            "warning"
        )
        return redirect(url_for("documents.my_documents"))

    flash("Document deleted successfully.", "success")
    return redirect(url_for("documents.my_documents"))
