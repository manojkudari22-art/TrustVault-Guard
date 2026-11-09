import uuid
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, request, redirect, url_for, flash, send_from_directory, render_template
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
        return redirect(url_for("auth.dashboard"))

    original_filename = secure_filename(uploaded_file.filename)

    if not original_filename:
        flash("Invalid filename.", "error")
        return redirect(url_for("auth.dashboard"))

    if not allowed_file(original_filename, uploaded_file.mimetype, uploaded_file.stream):
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
            Document.owner_id == current_user.id,
            Document.deleted_at.is_(None),
            DocumentPermission.is_active.is_(True)
        )
        .order_by(DocumentPermission.created_at.desc())
        .all()
    )

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
        active_permissions=active_permissions
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


@documents.route("/edit-content/<int:document_id>", methods=["GET", "POST"])
@login_required
def edit_document_content(document_id):
    import io

    document = db.session.get(Document, document_id)

    if document is None or document.deleted_at is not None:
        flash("Document not found.", "error")
        return redirect(url_for("auth.dashboard"))

    back_endpoint = (
        "documents.my_documents"
        if document.owner_id == current_user.id
        else "documents.shared_with_me"
    )

    extension = document.original_filename.rsplit(".", 1)[-1].lower()
    if extension not in {"txt", "csv"}:
        flash("Only TXT and CSV files support direct editing.", "error")
        return redirect(url_for(back_endpoint))

    is_owner = document.owner_id == current_user.id
    permission = None

    if not is_owner:
        permission = DocumentPermission.query.filter_by(
            document_id=document.id,
            user_id=current_user.id,
            is_active=True
        ).first()

    if not (
        is_owner or
        (permission is not None and permission.permission == "edit")
    ):
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
            back_endpoint=(
                "documents.my_documents"
                if is_owner
                else "documents.shared_with_me"
            )
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

    permission = None
    if not is_owner:
        permission = DocumentPermission.query.filter_by(
            document_id=document.id,
            user_id=current_user.id,
            is_active=True
        ).first()

    can_replace = (
        is_owner or
        (permission is not None and permission.permission == "edit")
    )

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
