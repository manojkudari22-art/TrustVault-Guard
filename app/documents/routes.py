import uuid
import json
import secrets
import io
import jwt
import pymupdf
import urllib.request
from urllib.request import HTTPRedirectHandler, build_opener
from urllib.parse import urlparse
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, request, redirect, url_for, flash, send_from_directory, render_template, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app import db, csrf
from app.documents.models import Document
from app.auth.models import User
from app.documents.permissions import DocumentPermission
from app.documents.edit_requests import DocumentEditRequest
from app.documents.editor_sessions import DocumentEditorSession
from app.audit.utils import log_audit_event
from app.ai.permission_advisor import suggest_permission

class NoRedirectHandler(HTTPRedirectHandler):
    """Prevent callback downloads from following redirects."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


documents = Blueprint("documents", __name__, url_prefix="/documents")


def _office_user_can_edit(document, user):
    """Check owner access or the administrator's latest approved request."""
    if document.owner_id == user.id:
        return True

    if user.role != "Administrator":
        return False

    latest_request = (
        DocumentEditRequest.query
        .filter_by(document_id=document.id, admin_id=user.id)
        .order_by(
            DocumentEditRequest.requested_at.desc(),
            DocumentEditRequest.id.desc()
        )
        .first()
    )

    return latest_request is not None and latest_request.status == "approved"


def _create_office_session_token(editor_session):
    """Create a short-lived application token for one editor session."""
    expires_at = editor_session.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    payload = {
        "purpose": "trustvault_office_editor",
        "session_id": editor_session.id,
        "document_id": editor_session.document_id,
        "user_id": editor_session.user_id,
        "exp": int(expires_at.timestamp()),
    }

    return jwt.encode(
        payload,
        current_app.config["SECRET_KEY"],
        algorithm="HS256"
    )


def _decode_office_session_token(token):
    """Validate a TrustVault editor token and its intended purpose."""
    if not token:
        return None

    try:
        payload = jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=["HS256"]
        )
    except jwt.InvalidTokenError:
        return None

    if payload.get("purpose") != "trustvault_office_editor":
        return None

    return payload


ALLOWED_EXTENSIONS = {
    "pdf": {"application/pdf"},
    "txt": {"text/plain"},
    "doc": {"application/msword"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    },
    "pptx": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    },
    "xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    },
    "csv": {
        "text/csv",
        "application/csv",
        "application/vnd.ms-excel",
    },
}

MAX_FILE_SIZES = {
    "pdf": 25 * 1024 * 1024,
    "doc": 15 * 1024 * 1024,
    "docx": 20 * 1024 * 1024,
    "pptx": 20 * 1024 * 1024,
    "xlsx": 20 * 1024 * 1024,
    "csv": 10 * 1024 * 1024,
    "txt": 5 * 1024 * 1024,
}


def validate_ooxml_archive(file_stream, extension):
    """Validate DOCX, PPTX and XLSX ZIP-based Office packages."""
    required_parts = {
        "docx": "word/document.xml",
        "pptx": "ppt/presentation.xml",
        "xlsx": "xl/workbook.xml",
    }
    expected_root_tags = {
        "docx": "document",
        "pptx": "presentation",
        "xlsx": "workbook",
    }

    try:
        file_stream.seek(0)

        with zipfile.ZipFile(file_stream) as archive:
            entries = archive.infolist()

            if not entries or len(entries) > 2000:
                return False

            names = set()
            total_uncompressed_size = 0

            for entry in entries:
                name = entry.filename

                if (
                    not name
                    or "\x00" in name
                    or "\\" in name
                    or name.startswith("/")
                    or ".." in Path(name).parts
                    or entry.flag_bits & 0x1
                ):
                    return False

                if name in names:
                    return False
                names.add(name)

                if entry.file_size < 0 or entry.compress_size < 0:
                    return False

                if entry.file_size > 50 * 1024 * 1024:
                    return False

                total_uncompressed_size += entry.file_size
                if total_uncompressed_size > 100 * 1024 * 1024:
                    return False

                if (
                    entry.file_size > 0
                    and entry.file_size / max(entry.compress_size, 1) > 200
                ):
                    return False

            required = {
                "[Content_Types].xml",
                required_parts[extension],
            }

            if not required.issubset(names):
                return False

            if archive.testzip() is not None:
                return False

            content_types_data = archive.read("[Content_Types].xml")
            main_part_data = archive.read(required_parts[extension])

            if len(content_types_data) > 1024 * 1024:
                return False

            if len(main_part_data) > 10 * 1024 * 1024:
                return False

            content_types_root = ET.fromstring(content_types_data)
            main_root = ET.fromstring(main_part_data)

            return (
                content_types_root.tag.endswith("}Types")
                and main_root.tag.endswith(
                    "}" + expected_root_tags[extension]
                )
            )

    except (
        OSError,
        zipfile.BadZipFile,
        ET.ParseError,
        KeyError,
        RuntimeError,
        ValueError,
    ):
        return False

    finally:
        file_stream.seek(0)


def validate_csv(file_stream):
    """Check CSV encoding and syntax without executing spreadsheet formulas."""
    import csv
    import io

    try:
        file_stream.seek(0)
        content = file_stream.read()

        if b"\x00" in content:
            return False

        text = content.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)

        row_count = 0

        for row in reader:
            row_count += 1

            if row_count > 100000 or len(row) > 1000:
                return False

            if any(len(field) > 1024 * 1024 for field in row):
                return False

        return True

    except (UnicodeDecodeError, csv.Error, ValueError):
        return False

    finally:
        file_stream.seek(0)


def allowed_file(filename, mimetype, file_stream):
    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()

    if (
        extension not in ALLOWED_EXTENSIONS
        or mimetype not in ALLOWED_EXTENSIONS[extension]
    ):
        return False

    try:
        file_stream.seek(0, 2)
        file_size = file_stream.tell()
        file_stream.seek(0)

        if file_size > MAX_FILE_SIZES[extension]:
            return False

        signature = file_stream.read(8)

        if extension == "pdf":
            return signature.startswith(b"%PDF-")

        if extension == "doc":
            return signature == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

        if extension in {"docx", "pptx", "xlsx"}:
            return validate_ooxml_archive(file_stream, extension)

        if extension == "txt":
            file_stream.seek(0)
            content = file_stream.read()

            if b"\x00" in content:
                return False

            content.decode("utf-8-sig")
            return True

        if extension == "csv":
            return validate_csv(file_stream)

        return False

    except (
        OSError,
        UnicodeDecodeError,
        zipfile.BadZipFile,
        ET.ParseError,
        KeyError,
        RuntimeError,
        ValueError,
    ):
        return False

    finally:
        file_stream.seek(0)


@documents.route("/upload", methods=["POST"])
@login_required
def upload_document():

    if current_user.role not in ["Document Owner", "Administrator"]:
        flash("You are not authorized to upload documents.", "error")
        return redirect(url_for("auth.dashboard"))

    uploaded_file = request.files.get("file")

    if not uploaded_file or not uploaded_file.filename:
        flash("Please select a file.", "error")
        return redirect(url_for("documents.upload_page"))

    original_filename = secure_filename(uploaded_file.filename)

    if not original_filename:
        flash("Invalid filename.", "error")
        return redirect(url_for("documents.upload_page"))

    if not allowed_file(original_filename, uploaded_file.mimetype, uploaded_file.stream):
        flash("File type is not allowed.", "error")
        return redirect(url_for("documents.upload_page"))

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
        db.session.flush()

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
    return redirect(url_for("documents.upload_page"))
from flask import render_template

@documents.route("/my-documents")
@login_required
def my_documents():
    if current_user.role not in ["Document Owner", "Administrator"]:
        flash("You are not authorized to view these documents.", "error")
        return redirect(url_for("auth.dashboard"))

    is_admin = current_user.role == "Administrator"

    query = Document.query.filter_by(deleted_at=None)
    if not is_admin:
        query = query.filter_by(owner_id=current_user.id)

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
        .filter(Document.deleted_at.is_(None))
        .filter(
            Document.owner_id == current_user.id
            if not is_admin else True
        )
        .distinct()
        .order_by(Document.category)
        .all()
    ]

    active_permissions = (
        db.session.query(
            DocumentPermission.document_id,
            DocumentPermission.user_id,
            User.username,
            DocumentPermission.permission
        )
        .join(User, User.id == DocumentPermission.user_id)
        .join(Document, Document.id == DocumentPermission.document_id)
        .filter(
            Document.deleted_at.is_(None),
            DocumentPermission.is_active.is_(True)
        )
        .filter(
            Document.owner_id == current_user.id
            if not is_admin else True
        )
        .order_by(DocumentPermission.created_at.desc())
        .all()
    )

    approved_admin_document_ids = set()

    if is_admin:
        latest_request_ids = (
            db.session.query(
                db.func.max(DocumentEditRequest.id).label("latest_id")
            )
            .filter_by(admin_id=current_user.id)
            .group_by(DocumentEditRequest.document_id)
            .subquery()
        )

        approved_admin_document_ids = {
            row.document_id
            for row in (
                db.session.query(DocumentEditRequest.document_id)
                .join(
                    latest_request_ids,
                    DocumentEditRequest.id == latest_request_ids.c.latest_id
                )
                .filter(DocumentEditRequest.status == "approved")
                .all()
            )
        }

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
        active_permissions=active_permissions,
        approved_admin_document_ids=approved_admin_document_ids,
        shared_mode=False
    )
@documents.route("/download/<int:document_id>")
@login_required
def download_document(document_id):
    document = db.session.get(Document, document_id)

    if document is None or document.deleted_at is not None:
        flash("Document not found.", "error")
        return redirect(url_for("auth.dashboard"))

    is_owner = document.owner_id == current_user.id
    is_admin = current_user.role == "Administrator"

    permission = None
    if not is_owner:
        permission = DocumentPermission.query.filter_by(
            document_id=document.id,
            user_id=current_user.id,
            is_active=True
        ).first()

    has_download_access = (
        is_admin or
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

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    stored_path = (upload_folder / document.stored_filename).resolve()

    if stored_path.parent != upload_folder or not stored_path.is_file():
        flash("Document file is unavailable or has an invalid storage path.", "error")
        return redirect(url_for("auth.dashboard"))

    log_audit_event(
        user_id=current_user.id,
        document_id=document.id,
        action="DOCUMENT_DOWNLOAD",
        details="Document downloaded successfully"
    )

    return send_from_directory(
        str(upload_folder),
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
    is_admin = current_user.role == "Administrator"

    permission = None
    if not is_owner:
        permission = DocumentPermission.query.filter_by(
            document_id=document.id,
            user_id=current_user.id,
            is_active=True
        ).first()

    has_view_access = (
        is_admin or
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

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    stored_path = (upload_folder / document.stored_filename).resolve()

    if stored_path.parent != upload_folder or not stored_path.is_file():
        flash("Document file is unavailable or has an invalid storage path.", "error")
        return redirect(url_for("auth.dashboard"))

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








@documents.route("/office-callback/<int:session_id>", methods=["POST"])
@csrf.exempt
def office_editor_callback(session_id):
    def callback_error(message, status_code=403):
        return jsonify({"error": message}), status_code

    app_token = _decode_office_session_token(request.args.get("token"))
    if not app_token or app_token.get("session_id") != session_id:
        return callback_error("Invalid editor session token", 401)

    authorization = request.headers.get("Authorization", "").strip()
    office_token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else authorization

    if not office_token:
        return callback_error("Missing Document Server authorization", 401)

    try:
        office_claims = jwt.decode(
            office_token,
            current_app.config["ONLYOFFICE_JWT_SECRET"],
            algorithms=["HS256"],
        )
    except jwt.InvalidTokenError:
        return callback_error("Invalid Document Server authorization", 401)

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return callback_error("Invalid callback body", 400)

    for field in ("key", "status"):
        if office_claims.get(field) != body.get(field):
            return callback_error("Callback token does not match its payload", 401)

    if body.get("url") is not None and office_claims.get("url") != body.get("url"):
        return callback_error("Callback URL does not match its signed payload", 401)

    editor_session = db.session.get(DocumentEditorSession, session_id)
    if (
        editor_session is None
        or editor_session.status != "active"
        or app_token.get("document_id") != editor_session.document_id
        or app_token.get("user_id") != editor_session.user_id
    ):
        return callback_error("Editor session is inactive", 403)

    expires_at = editor_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at <= datetime.now(timezone.utc):
        return callback_error("Editor session has expired", 403)

    if body.get("key") != editor_session.document_key:
        return callback_error("Document key mismatch", 403)

    status = body.get("status")

    if status == 4:
        editor_session.status = "closed"
        editor_session.closed_at = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify({"error": 0})

    if status not in (2, 6):
        return jsonify({"error": 0})

    document = db.session.get(Document, editor_session.document_id)
    user = db.session.get(User, editor_session.user_id)

    if (
        document is None
        or user is None
        or getattr(document, "deleted_at", None) is not None
        or not _office_user_can_edit(document, user)
    ):
        return callback_error("Document edit authorization is no longer valid", 403)

    if document.stored_filename != editor_session.last_saved_filename:
        return callback_error("Document was changed by another session", 409)

    callback_url = body.get("url")
    if not isinstance(callback_url, str):
        return callback_error("Missing saved document URL", 400)

    parsed_url = urlparse(callback_url)
    allowed_hosts = {
        "localhost",
        "127.0.0.1",
        "host.docker.internal",
        "onlyoffice-document-server",
    }

    try:
        callback_port = parsed_url.port
    except ValueError:
        return callback_error("Untrusted Document Server URL", 403)

    if (
        parsed_url.scheme not in ("http", "https")
        or parsed_url.hostname not in allowed_hosts
        or parsed_url.username
        or parsed_url.password
        or callback_port not in (None, 80, 8080)
    ):
        return callback_error("Untrusted Document Server URL", 403)

    extension = document.original_filename.rsplit(".", 1)[-1].lower()
    if extension not in ("docx", "xlsx", "pptx"):
        return callback_error("Unsupported document format", 400)

    max_size = MAX_FILE_SIZES.get(extension, 20 * 1024 * 1024)

    try:
        class _NoRedirectHandler(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        download_request = urllib.request.Request(
            callback_url,
            headers={"User-Agent": "TrustVault-Document-Saver/1.0"},
        )

        opener = build_opener(NoRedirectHandler())

        with opener.open(download_request, timeout=30) as response:
            data = response.read(max_size + 1)

        if not data or len(data) > max_size:
            return callback_error("Saved document is empty or exceeds the size limit", 413)

        if not validate_ooxml_archive(io.BytesIO(data), extension):
            return callback_error("Saved document failed Office file validation", 400)

    except Exception:
        current_app.logger.exception("Unable to retrieve the saved ONLYOFFICE document")
        return callback_error("Unable to retrieve the saved document", 502)

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    upload_folder.mkdir(parents=True, exist_ok=True)

    new_filename = f"{uuid.uuid4().hex}.{extension}"
    new_path = upload_folder / new_filename
    old_path = (upload_folder / document.stored_filename).resolve()

    if old_path.parent != upload_folder:
        return callback_error("Invalid existing document path", 400)

    try:
        with new_path.open("xb") as output_file:
            output_file.write(data)

        document.stored_filename = new_filename
        editor_session.last_saved_filename = new_filename
        editor_session.last_saved_at = datetime.now(timezone.utc)

        if status == 2:
            editor_session.status = "closed"
            editor_session.closed_at = datetime.now(timezone.utc)

        log_audit_event(
            user_id=user.id,
            document_id=document.id,
            action="DOCUMENT_OFFICE_EDITED",
            details=f"Saved online {extension.upper()} document changes (callback status {status})",
        )

        db.session.commit()

    except Exception:
        db.session.rollback()
        new_path.unlink(missing_ok=True)
        current_app.logger.exception("Unable to save ONLYOFFICE document changes")
        return callback_error("Unable to save document changes", 500)

    if old_path != new_path:
        try:
            old_path.unlink(missing_ok=True)
        except OSError:
            current_app.logger.exception("Unable to remove the previous document version")

    return jsonify({"error": 0})


@documents.route("/office-file/<int:session_id>", methods=["GET"])
def office_editor_file(session_id):
    token_payload = _decode_office_session_token(request.args.get("token"))

    if not token_payload or token_payload.get("session_id") != session_id:
        return jsonify({"error": "Invalid editor session"}), 401

    editor_session = db.session.get(DocumentEditorSession, session_id)

    if (
        editor_session is None
        or editor_session.status != "active"
        or editor_session.expires_at.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc)
        or token_payload.get("document_id") != editor_session.document_id
        or token_payload.get("user_id") != editor_session.user_id
    ):
        return jsonify({"error": "Expired or inactive editor session"}), 403

    document = db.session.get(Document, editor_session.document_id)
    user = db.session.get(User, editor_session.user_id)

    if (
        document is None
        or user is None
        or getattr(document, "deleted_at", None) is not None
        or not _office_user_can_edit(document, user)
    ):
        return jsonify({"error": "Document access is no longer authorized"}), 403

    if document.stored_filename != editor_session.last_saved_filename:
        return jsonify({"error": "Document version has changed"}), 409

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    stored_path = (upload_folder / document.stored_filename).resolve()

    if stored_path.parent != upload_folder or not stored_path.is_file():
        return jsonify({"error": "Document file unavailable"}), 404

    response = send_from_directory(
        upload_folder,
        document.stored_filename,
        as_attachment=False,
        download_name=document.original_filename,
    )
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@documents.route("/edit-online/<int:document_id>", methods=["GET"])
@login_required
def edit_document_online(document_id):
    document = Document.query.get_or_404(document_id)

    if not _office_user_can_edit(document, current_user):
        log_audit_event(
            current_user.id,
            document.id,
            "ACCESS_DENIED",
            "Unauthorized online document editing attempt"
        )
        flash("You are not authorized to edit this document.", "error")
        return redirect(url_for("documents.my_documents"))

    extension = document.original_filename.rsplit(".", 1)[-1].lower()

    document_types = {
        "docx": "word",
        "xlsx": "cell",
        "pptx": "slide",
    }

    if extension not in document_types:
        flash("Online editing is not yet enabled for this file type.", "error")
        return redirect(url_for("documents.my_documents"))

    server_url = current_app.config.get("ONLYOFFICE_DOCUMENT_SERVER", "").rstrip("/")
    jwt_secret = current_app.config.get("ONLYOFFICE_JWT_SECRET", "")
    internal_url = current_app.config.get("ONLYOFFICE_INTERNAL_BASE_URL", "").rstrip("/")

    if not server_url or not jwt_secret or not internal_url:
        flash("The online document editor is not configured.", "error")
        return redirect(url_for("documents.my_documents"))

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    stored_path = (upload_folder / document.stored_filename).resolve()

    if stored_path.parent != upload_folder or not stored_path.is_file():
        flash("The document file could not be found.", "error")
        return redirect(url_for("documents.my_documents"))

    now = datetime.now(timezone.utc)
    editor_session = DocumentEditorSession(
        document_key=uuid.uuid4().hex,
        session_key=secrets.token_urlsafe(32),
        document_id=document.id,
        user_id=current_user.id,
        original_stored_filename=document.stored_filename,
        last_saved_filename=document.stored_filename,
        status="active",
        expires_at=now + timedelta(hours=24),
    )

    try:
        db.session.add(editor_session)
        db.session.flush()

        app_token = _create_office_session_token(editor_session)

        file_path = url_for(
            "documents.office_editor_file",
            session_id=editor_session.id,
            _external=False,
        )
        callback_path = url_for(
            "documents.office_editor_callback",
            session_id=editor_session.id,
            _external=False,
        )

        file_url = f"{internal_url}{file_path}?token={app_token}"
        callback_url = f"{internal_url}{callback_path}?token={app_token}"

        editor_config = {
            "documentType": document_types[extension],
            "document": {
                "fileType": extension,
                "key": editor_session.document_key,
                "title": document.original_filename,
                "url": file_url,
                "permissions": {
                    "edit": True,
                    "download": True,
                    "print": True,
                },
            },
            "editorConfig": {
                "callbackUrl": callback_url,
                "mode": "edit",
                "user": {
                    "id": str(current_user.id),
                    "name": getattr(current_user, "username", None) or "TrustVault User",
                },
                "customization": {
                    "forcesave": True,
                },
            },
        }

        editor_config["token"] = jwt.encode(
            editor_config,
            jwt_secret,
            algorithm="HS256",
        )

        db.session.commit()

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Unable to create ONLYOFFICE editor session")
        flash("Unable to start the online editor. Please try again.", "error")
        return redirect(url_for("documents.my_documents"))

    return render_template(
        "documents/office_editor.html",
        document=document,
        editor_config=editor_config,
        document_server_url=server_url,
        back_endpoint="documents.my_documents",
    )


@documents.route("/edit-content/<int:document_id>", methods=["GET", "POST"])
@login_required
def edit_document_content(document_id):
    import io

    document = db.session.get(Document, document_id)

    if document is None or document.deleted_at is not None:
        flash("Document not found.", "error")
        return redirect(url_for("auth.dashboard"))

    is_owner = document.owner_id == current_user.id
    is_admin = current_user.role == "Administrator"

    back_endpoint = (
        "documents.my_documents"
        if is_owner or is_admin
        else "documents.shared_with_me"
    )

    extension = document.original_filename.rsplit(".", 1)[-1].lower()
    if extension not in {"txt", "csv"}:
        flash("Only TXT and CSV files support direct editing.", "error")
        return redirect(url_for(back_endpoint))

    latest_edit_request = None

    if is_admin and not is_owner:
        latest_edit_request = (
            DocumentEditRequest.query
            .filter_by(
                document_id=document.id,
                admin_id=current_user.id
            )
            .order_by(
                DocumentEditRequest.requested_at.desc(),
                DocumentEditRequest.id.desc()
            )
            .first()
        )

    admin_approved = (
        is_admin
        and latest_edit_request is not None
        and latest_edit_request.status == "approved"
    )

    if not (is_owner or admin_approved):
        log_audit_event(
            current_user.id,
            document.id,
            "ACCESS_DENIED",
            "Unauthorized document content editing attempt"
        )
        flash("You are not authorized to edit this document.", "error")
        return redirect(url_for(back_endpoint))

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    old_path = (upload_folder / document.stored_filename).resolve()

    if old_path.parent != upload_folder or not old_path.is_file():
        flash("Document file is unavailable or has an invalid storage path.", "error")
        return redirect(url_for(back_endpoint))

    if request.method == "GET":
        try:
            if old_path.stat().st_size > 10 * 1024 * 1024:
                flash("This file is too large for the online editor.", "error")
                return redirect(url_for(back_endpoint))

            content = old_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            flash("Unable to read this file as UTF-8 text.", "error")
            return redirect(url_for(back_endpoint))

        return render_template(
            "documents/editor.html",
            document=document,
            content=content,
            extension=extension,
            back_endpoint=back_endpoint
        )

    content = request.form.get("content", "")
    new_bytes = content.encode("utf-8")

    if len(new_bytes) > 10 * 1024 * 1024 or b"\x00" in new_bytes:
        flash("Content is invalid or exceeds the 10 MB editor limit.", "error")
        return redirect(url_for("documents.edit_document_content", document_id=document.id))

    if extension == "csv" and not validate_csv(io.BytesIO(new_bytes)):
        flash("Invalid CSV content. Please correct it before saving.", "error")
        return redirect(url_for("documents.edit_document_content", document_id=document.id))

    new_filename = f"{uuid.uuid4().hex}.{extension}"
    new_path = upload_folder / new_filename

    try:
        new_path.write_bytes(new_bytes)
        document.stored_filename = new_filename
        db.session.flush()

        log_audit_event(
            current_user.id,
            document.id,
            "DOCUMENT_CONTENT_EDITED",
            f"Edited {extension.upper()} document content"
        )

    except Exception:
        db.session.rollback()
        try:
            new_path.unlink(missing_ok=True)
        except OSError:
            current_app.logger.exception("Unable to remove failed editor file")

        current_app.logger.exception("Document content editing failed")
        flash("Unable to save document changes.", "error")
        return redirect(url_for("documents.edit_document_content", document_id=document.id))

    try:
        old_path.unlink(missing_ok=True)
    except OSError:
        current_app.logger.exception("Unable to remove previous document version")

    flash("Document content saved successfully.", "success")
    return redirect(url_for("documents.edit_document_content", document_id=document.id))


@documents.route("/upload", methods=["GET"])
@login_required
def upload_page():
    if current_user.role not in ["Document Owner", "Administrator"]:
        flash("You are not authorized to upload documents.", "error")
        return redirect(url_for("auth.dashboard"))

    return render_template("documents/upload.html")





@documents.route("/ai-suggest/<int:document_id>", methods=["POST"])
@login_required
def ai_suggest_permission(document_id):
    document = db.session.get(Document, document_id)

    if (
        document is None
        or document.deleted_at is not None
        or document.owner_id != current_user.id
    ):
        return jsonify({"error": "You are not authorized to request suggestions."}), 403

    sharing_reason = request.form.get("reason", "").strip()
    username = request.form.get("username", "").strip()

    if not sharing_reason or len(sharing_reason) > 500:
        return jsonify({"error": "Enter a sharing reason (maximum 500 characters)."}), 400

    if not username or len(username) > 100:
        return jsonify({"error": "Enter a valid recipient username."}), 400

    recipient = User.query.filter(
        User.username == username,
        User.is_active.is_(True),
        User.id != current_user.id,
        User.role.in_(["Viewer", "Document Owner"])
    ).first()

    if recipient is None:
        return jsonify({"error": "Recipient not found or not eligible for sharing."}), 400

    existing_permission = DocumentPermission.query.filter_by(
        document_id=document.id,
        user_id=recipient.id,
        is_active=True
    ).first()

    if existing_permission:
        return jsonify({"error": "This recipient already has active access."}), 400

    candidates = [
        {"username": recipient.username, "role": recipient.role}
    ]

    recommendation = suggest_permission(
        document_name=document.name,
        category=document.category,
        sharing_reason=sharing_reason,
        candidates=candidates
    )

    if "error" in recommendation:
        return jsonify(recommendation), 503

    return jsonify({
        "success": True,
        "recommendation": recommendation,
        "message": "Review this suggestion before sharing. No access has been granted."
    }), 200

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

    flash("Document shared successfully.", "share_success")
    return redirect(url_for("documents.my_documents", shared_document=document.id))


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





@documents.route("/request-edit/<int:document_id>", methods=["POST"])
@login_required
def request_admin_edit_access(document_id):
    document = db.session.get(Document, document_id)

    if current_user.role != "Administrator":
        flash("Only administrators can request this access.", "error")
        return redirect(url_for("documents.my_documents"))

    if document is None or document.deleted_at is not None:
        flash("Document not found.", "error")
        return redirect(url_for("documents.my_documents"))

    if document.owner_id == current_user.id:
        flash("You already own this document.", "error")
        return redirect(url_for("documents.my_documents"))

    existing_request = DocumentEditRequest.query.filter_by(
        document_id=document.id,
        admin_id=current_user.id,
        status="pending"
    ).first()

    if existing_request:
        flash("An edit request is already pending.", "info")
        return redirect(url_for("documents.my_documents"))

    try:
        edit_request = DocumentEditRequest(
            document_id=document.id,
            admin_id=current_user.id,
            owner_id=document.owner_id,
            status="pending"
        )
        db.session.add(edit_request)

        log_audit_event(
            user_id=current_user.id,
            document_id=document.id,
            action="ADMIN_EDIT_REQUESTED",
            details=f"Administrator requested edit access for document {document.id}"
        )

        db.session.commit()

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Admin edit request failed")
        flash("Unable to submit edit request.", "error")
        return redirect(url_for("documents.my_documents"))

    flash("Edit request sent to the document owner.", "success")
    return redirect(url_for("documents.my_documents"))



@documents.route("/edit-requests")
@login_required
def owner_edit_requests():
    if current_user.role != "Document Owner":
        flash("Only document owners can review edit requests.", "error")
        return redirect(url_for("auth.dashboard"))

    edit_requests = (
        DocumentEditRequest.query
        .filter_by(owner_id=current_user.id)
        .join(Document, Document.id == DocumentEditRequest.document_id)
        .filter(Document.deleted_at.is_(None))
        .order_by(DocumentEditRequest.requested_at.desc())
        .all()
    )

    return render_template(
        "documents/edit_requests.html",
        edit_requests=edit_requests
    )



@documents.route("/edit-request/<int:request_id>/<decision>", methods=["POST"])
@login_required
def respond_admin_edit_request(request_id, decision):
    if current_user.role != "Document Owner":
        flash("Only document owners can respond to edit requests.", "error")
        return redirect(url_for("auth.dashboard"))

    if decision not in {"approve", "reject"}:
        flash("Invalid request decision.", "error")
        return redirect(url_for("documents.owner_edit_requests"))

    edit_request = db.session.get(DocumentEditRequest, request_id)

    if (
        edit_request is None
        or edit_request.owner_id != current_user.id
        or edit_request.status != "pending"
    ):
        flash("Pending edit request not found.", "error")
        return redirect(url_for("documents.owner_edit_requests"))

    document = db.session.get(Document, edit_request.document_id)

    if document is None or document.deleted_at is not None:
        flash("The requested document is no longer available.", "error")
        return redirect(url_for("documents.owner_edit_requests"))

    try:
        edit_request.status = (
            "approved" if decision == "approve" else "rejected"
        )
        edit_request.responded_at = datetime.now(timezone.utc)

        log_audit_event(
            user_id=current_user.id,
            document_id=document.id,
            action=(
                "ADMIN_EDIT_APPROVED"
                if decision == "approve"
                else "ADMIN_EDIT_REJECTED"
            ),
            details=(
                f"Owner {decision}d edit request "
                f"from administrator ID {edit_request.admin_id}"
            )
        )

        db.session.commit()

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Admin edit request response failed")
        flash("Unable to process the edit request.", "error")
        return redirect(url_for("documents.owner_edit_requests"))

    flash(
        "Administrator edit access approved."
        if decision == "approve"
        else "Administrator edit request rejected.",
        "success"
    )
    return redirect(url_for("documents.owner_edit_requests"))

@documents.route("/edit-request/<int:request_id>/revoke", methods=["POST"])
@login_required
def revoke_admin_edit_approval(request_id):
    if current_user.role != "Document Owner":
        flash("Only document owners can revoke edit access.", "error")
        return redirect(url_for("auth.dashboard"))

    edit_request = db.session.get(DocumentEditRequest, request_id)

    if (
        edit_request is None
        or edit_request.owner_id != current_user.id
        or edit_request.status != "approved"
    ):
        flash("Approved edit request not found.", "error")
        return redirect(url_for("documents.owner_edit_requests"))

    document = db.session.get(Document, edit_request.document_id)

    if document is None or document.deleted_at is not None:
        flash("The requested document is no longer available.", "error")
        return redirect(url_for("documents.owner_edit_requests"))

    try:
        edit_request.status = "revoked"
        edit_request.responded_at = datetime.now(timezone.utc)

        log_audit_event(
            user_id=current_user.id,
            document_id=document.id,
            action="ADMIN_EDIT_REVOKED",
            details=f"Owner revoked edit access for administrator ID {edit_request.admin_id}"
        )

        db.session.commit()

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Admin edit approval revocation failed")
        flash("Unable to revoke administrator edit access.", "error")
        return redirect(url_for("documents.owner_edit_requests"))

    flash("Administrator edit access revoked successfully.", "success")
    return redirect(url_for("documents.owner_edit_requests"))


@documents.route("/shared-by-me")
@login_required
def shared_by_me():
    from sqlalchemy import or_

    if current_user.role not in ["Document Owner", "Administrator"]:
        flash("You are not authorized to view your shared documents.", "error")
        return redirect(url_for("auth.dashboard"))

    query = (
        db.session.query(DocumentPermission, Document, User.username)
        .join(Document, Document.id == DocumentPermission.document_id)
        .join(User, User.id == DocumentPermission.user_id)
        .filter(
            Document.owner_id == current_user.id,
            Document.deleted_at.is_(None)
        )
    )

    search = request.args.get("q", "").strip()[:100]
    if search:
        query = query.filter(
            or_(
                Document.name.ilike(f"%{search}%"),
                User.username.ilike(f"%{search}%")
            )
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
    total_records = query.count()
    total_pages = max(1, (total_records + per_page - 1) // per_page)
    page = min(page, total_pages)

    shares = (
        query.order_by(DocumentPermission.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return render_template(
        "documents/shared_by_me.html",
        shares=shares,
        search=search,
        page=page,
        total_pages=total_pages,
        total_records=total_records
    )

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
        if permission is None:
            continue
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

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    file_path = (upload_folder / document.stored_filename).resolve()

    if file_path.parent != upload_folder or not file_path.is_file():
        flash("Document file is unavailable or has an invalid storage path.", "error")
        return redirect(url_for("documents.my_documents"))

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

@documents.route("/replace/<int:document_id>", methods=["POST"])
@login_required
def replace_document_content(document_id):
    document = db.session.get(Document, document_id)

    if document is None or document.deleted_at is not None:
        flash("Document not found.", "error")
        return redirect(url_for("documents.my_documents"))

    is_owner = document.owner_id == current_user.id
    is_admin = current_user.role == "Administrator"

    latest_edit_request = None

    if is_admin and not is_owner:
        latest_edit_request = (
            DocumentEditRequest.query
            .filter_by(
                document_id=document.id,
                admin_id=current_user.id
            )
            .order_by(
                DocumentEditRequest.requested_at.desc(),
                DocumentEditRequest.id.desc()
            )
            .first()
        )

    admin_approved = (
        is_admin
        and latest_edit_request is not None
        and latest_edit_request.status == "approved"
    )

    can_replace = is_owner or admin_approved

    if not can_replace:
        log_audit_event(
            user_id=current_user.id,
            document_id=document.id,
            action="ACCESS_DENIED",
            details="Unauthorized document content replacement attempt"
        )
        flash("You are not authorized to replace this document.", "error")
        return redirect(url_for("documents.my_documents"))

    uploaded_file = request.files.get("file")

    if not uploaded_file or not uploaded_file.filename:
        flash("Please select a replacement file.", "error")
        return redirect(url_for("documents.my_documents"))

    original_filename = secure_filename(uploaded_file.filename)

    if not original_filename or not allowed_file(
        original_filename, uploaded_file.mimetype, uploaded_file.stream
    ):
        flash("File type is not allowed.", "error")
        return redirect(url_for("documents.my_documents"))

    extension = original_filename.rsplit(".", 1)[1].lower()
    new_stored_filename = f"{uuid.uuid4().hex}.{extension}"

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    upload_folder.mkdir(parents=True, exist_ok=True)

    new_file_path = upload_folder / new_stored_filename
    old_file_path = (upload_folder / document.stored_filename).resolve()

    if old_file_path.parent != upload_folder or not old_file_path.is_file():
        flash("Original document is unavailable or has an invalid storage path.", "error")
        return redirect(url_for("documents.my_documents"))

    old_stored_filename = document.stored_filename
    old_original_filename = document.original_filename

    try:
        uploaded_file.save(new_file_path)

        document.stored_filename = new_stored_filename
        document.original_filename = original_filename
        document.name = original_filename

        log_audit_event(
            user_id=current_user.id,
            document_id=document.id,
            action="DOCUMENT_CONTENT_REPLACED",
            details=(
                f"Replaced document content. "
                f"Previous file: {old_original_filename}; "
                f"New file: {original_filename}"
            )
        )

    except Exception:
        db.session.rollback()
        try:
            new_file_path.unlink(missing_ok=True)
        except OSError:
            current_app.logger.exception(
                "Unable to remove failed replacement file"
            )

        current_app.logger.exception("Document content replacement failed")
        flash("Unable to replace document content.", "error")
        return redirect(url_for("documents.my_documents"))

    try:
        if old_file_path.exists():
            old_file_path.unlink()
    except OSError:
        current_app.logger.exception(
            "Old file cleanup failed for document ID %s", document.id
        )
        flash(
            "Document replaced, but old file cleanup needs attention.",
            "warning"
        )
        return redirect(url_for("documents.my_documents"))

    flash("Document content replaced successfully.", "success")
    return redirect(url_for("documents.my_documents"))


# ---------------------------------------------------------------------------
# Secure PDF annotation editor
# ---------------------------------------------------------------------------

@documents.route("/edit-pdf/<int:document_id>", methods=["GET"])
@login_required
def edit_pdf_document(document_id):
    document = db.session.get(Document, document_id)

    if document is None or document.deleted_at is not None:
        flash("Document not found.", "error")
        return redirect(url_for("documents.my_documents"))

    if not _office_user_can_edit(document, current_user):
        log_audit_event(
            current_user.id,
            document.id,
            "ACCESS_DENIED",
            "Unauthorized PDF editing attempt"
        )
        flash("You are not authorized to edit this PDF.", "error")
        return redirect(url_for("documents.my_documents"))

    if document.original_filename.rsplit(".", 1)[-1].lower() != "pdf":
        flash("This editor supports PDF files only.", "error")
        return redirect(url_for("documents.my_documents"))

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    stored_path = (upload_folder / document.stored_filename).resolve()

    if stored_path.parent != upload_folder or not stored_path.is_file():
        flash("PDF file is unavailable.", "error")
        return redirect(url_for("documents.my_documents"))

    if stored_path.stat().st_size > MAX_FILE_SIZES["pdf"]:
        flash("PDF exceeds the 25 MB editor limit.", "error")
        return redirect(url_for("documents.my_documents"))

    try:
        pdf = pymupdf.open(str(stored_path))
        if pdf.is_encrypted:
            pdf.close()
            flash("Password-protected PDFs are not supported yet.", "error")
            return redirect(url_for("documents.my_documents"))

        page_count = pdf.page_count
        pdf.close()

        if page_count < 1 or page_count > 200:
            flash("PDF must contain between 1 and 200 pages.", "error")
            return redirect(url_for("documents.my_documents"))

    except Exception:
        current_app.logger.exception("PDF validation failed")
        flash("This PDF is damaged or cannot be opened.", "error")
        return redirect(url_for("documents.my_documents"))

    return render_template(
        "documents/pdf_editor.html",
        document=document,
        page_count=page_count,
        document_version=document.stored_filename,
        back_endpoint="documents.my_documents",
    )


@documents.route(
    "/pdf-page/<int:document_id>/<int:page_number>",
    methods=["GET"]
)
@login_required
def pdf_page_preview(document_id, page_number):
    document = db.session.get(Document, document_id)

    if (
        document is None
        or document.deleted_at is not None
        or not _office_user_can_edit(document, current_user)
    ):
        return jsonify({"error": "Access denied"}), 403

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    stored_path = (upload_folder / document.stored_filename).resolve()

    if (
        stored_path.parent != upload_folder
        or not stored_path.is_file()
        or stored_path.stat().st_size > MAX_FILE_SIZES["pdf"]
    ):
        return jsonify({"error": "PDF unavailable"}), 404

    try:
        with pymupdf.open(str(stored_path)) as pdf:
            if pdf.is_encrypted or page_number < 0 or page_number >= pdf.page_count:
                return jsonify({"error": "Invalid PDF page"}), 400

            page = pdf.load_page(page_number)

            if page.rect.width * page.rect.height > 16_000_000:
                return jsonify({"error": "PDF page dimensions exceed preview limit"}), 413

            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(1.25, 1.25),
                alpha=False
            )
            image_bytes = pixmap.tobytes("png")

        response = current_app.response_class(
            image_bytes,
            mimetype="image/png"
        )
        response.headers["Cache-Control"] = "no-store, private"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    except Exception:
        current_app.logger.exception("PDF page preview failed")
        return jsonify({"error": "Unable to render PDF page"}), 422


@documents.route(
    "/edit-pdf/<int:document_id>/save",
    methods=["POST"]
)
@login_required
def save_pdf_annotations(document_id):
    document = db.session.get(Document, document_id)

    if document is None or document.deleted_at is not None:
        return jsonify({"error": "Document not found"}), 404

    if not _office_user_can_edit(document, current_user):
        log_audit_event(
            current_user.id,
            document.id,
            "ACCESS_DENIED",
            "Unauthorized PDF annotation save attempt"
        )
        return jsonify({"error": "You are not authorized to edit this PDF"}), 403

    if document.original_filename.rsplit(".", 1)[-1].lower() != "pdf":
        return jsonify({"error": "PDF files only"}), 400

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid request body"}), 400

    if payload.get("version") != document.stored_filename:
        return jsonify({
            "error": "This PDF has changed. Reload it before saving."
        }), 409

    operations = payload.get("operations")

    if (
        not isinstance(operations, list)
        or not operations
        or len(operations) > 500
    ):
        return jsonify({"error": "Invalid annotation list"}), 400

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    old_path = (upload_folder / document.stored_filename).resolve()

    if (
        old_path.parent != upload_folder
        or not old_path.is_file()
        or old_path.stat().st_size > MAX_FILE_SIZES["pdf"]
    ):
        return jsonify({"error": "Original PDF unavailable"}), 404

    new_filename = f"{uuid.uuid4().hex}.pdf"
    new_path = upload_folder / new_filename

    try:
        with pymupdf.open(str(old_path)) as pdf:
            if pdf.is_encrypted or pdf.page_count < 1 or pdf.page_count > 200:
                return jsonify({"error": "Unsupported PDF"}), 400

            for operation in operations:
                if not isinstance(operation, dict):
                    raise ValueError("Invalid annotation operation")

                page_number = operation.get("page")

                if (
                    isinstance(page_number, bool)
                    or not isinstance(page_number, int)
                    or page_number < 0
                    or page_number >= pdf.page_count
                ):
                    raise ValueError("Invalid page number")

                page = pdf.load_page(page_number)
                width = page.rect.width
                height = page.rect.height
                kind = operation.get("type")

                if kind == "text":
                    text = operation.get("text")
                    x = operation.get("x")
                    y = operation.get("y")
                    font_size = operation.get("font_size", 12)

                    if (
                        not isinstance(text, str)
                        or not text.strip()
                        or len(text) > 1000
                        or not isinstance(x, (int, float))
                        or not isinstance(y, (int, float))
                        or not isinstance(font_size, (int, float))
                        or isinstance(x, bool)
                        or isinstance(y, bool)
                        or isinstance(font_size, bool)
                        or not 0 <= x <= 1
                        or not 0 <= y <= 1
                        or not 6 <= font_size <= 48
                    ):
                        raise ValueError("Invalid text annotation")

                    left = x * width
                    top = y * height
                    rect = pymupdf.Rect(
                        left,
                        top,
                        min(left + 240, width),
                        min(top + max(40, font_size * 3), height)
                    )

                    if rect.width < 20 or rect.height < 15:
                        raise ValueError("Text position is outside the page")

                    annotation = page.add_freetext_annot(
                        rect,
                        text,
                        fontsize=font_size,
                        fontname="Helv",
                        text_color=(0, 0, 0),
                        fill_color=None,
                        border_color=None,
                    )
                    annotation.update()

                elif kind == "highlight":
                    x = operation.get("x")
                    y = operation.get("y")
                    w = operation.get("width")
                    h = operation.get("height")

                    values = (x, y, w, h)
                    if (
                        any(
                            isinstance(v, bool) or not isinstance(v, (int, float))
                            for v in values
                        )
                        or x < 0 or y < 0 or w <= 0 or h <= 0
                        or x + w > 1 or y + h > 1
                    ):
                        raise ValueError("Invalid highlight area")

                    rect = pymupdf.Rect(
                        x * width,
                        y * height,
                        (x + w) * width,
                        (y + h) * height,
                    )
                    annotation = page.add_highlight_annot(rect)
                    annotation.set_colors(stroke=(1, 1, 0))
                    annotation.update()

                elif kind == "draw":
                    points = operation.get("points")

                    if (
                        not isinstance(points, list)
                        or not 2 <= len(points) <= 2000
                    ):
                        raise ValueError("Invalid drawing points")

                    stroke = []
                    for point in points:
                        if (
                            not isinstance(point, (list, tuple))
                            or len(point) != 2
                            or any(
                                isinstance(v, bool)
                                or not isinstance(v, (int, float))
                                for v in point
                            )
                            or not 0 <= point[0] <= 1
                            or not 0 <= point[1] <= 1
                        ):
                            raise ValueError("Invalid drawing coordinates")

                        stroke.append([
                            point[0] * width,
                            point[1] * height
                        ])

                    annotation = page.add_ink_annot([stroke])
                    annotation.set_colors(stroke=(0.1, 0.7, 1))
                    annotation.set_border(width=2)
                    annotation.update()

                else:
                    raise ValueError("Unsupported annotation type")

            pdf.save(
                str(new_path),
                garbage=4,
                deflate=True
            )

        if (
            not new_path.is_file()
            or new_path.stat().st_size == 0
            or new_path.stat().st_size > MAX_FILE_SIZES["pdf"]
        ):
            raise ValueError("Edited PDF is empty or exceeds the 25 MB limit")

        with pymupdf.open(str(new_path)) as verified_pdf:
            if verified_pdf.is_encrypted or verified_pdf.page_count < 1:
                raise ValueError("Edited PDF validation failed")

        updated_rows = (
            db.session.query(Document)
            .filter(
                Document.id == document.id,
                Document.stored_filename == payload["version"],
            )
            .update(
                {Document.stored_filename: new_filename},
                synchronize_session=False,
            )
        )

        if updated_rows != 1:
            db.session.rollback()
            new_path.unlink(missing_ok=True)
            return jsonify({
                "error": "This PDF was saved by another session. Reload it before saving."
            }), 409

        log_audit_event(
            current_user.id,
            document.id,
            "DOCUMENT_PDF_ANNOTATED",
            json.dumps({
                "annotation_count": len(operations),
                "annotation_types": [
                    operation.get("type") for operation in operations
                ],
            })
        )

        db.session.commit()

    except ValueError as exc:
        db.session.rollback()
        new_path.unlink(missing_ok=True)
        return jsonify({"error": str(exc)}), 400

    except Exception:
        db.session.rollback()
        new_path.unlink(missing_ok=True)
        current_app.logger.exception("PDF annotation save failed")
        return jsonify({"error": "Unable to save PDF changes"}), 500

    try:
        old_path.unlink(missing_ok=True)
    except OSError:
        current_app.logger.exception(
            "Previous PDF version cleanup failed for document ID %s",
            document.id
        )

    return jsonify({
        "success": True,
        "message": "PDF annotations saved successfully.",
        "version": new_filename,
    }), 200



