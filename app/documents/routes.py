import uuid
from pathlib import Path

from flask import Blueprint, current_app, request, redirect, url_for, flash, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app import db
from app.documents.models import Document
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

    my_documents = Document.query.filter_by(
        owner_id=current_user.id
    ).order_by(Document.uploaded_at.desc()).all()

    return render_template(
        "documents/list.html",
        documents=my_documents
    )

@documents.route("/download/<int:document_id>")
@login_required
def download_document(document_id):

    document = db.session.get(Document, document_id)

    if document is None:
        flash("Document not found.", "error")
        return redirect(url_for("documents.my_documents"))

    if document.owner_id != current_user.id:
        log_audit_event(
            user_id=current_user.id,
            document_id=document.id,
            action="ACCESS_DENIED",
            details="Unauthorized document download attempt"
        )

        flash("You are not authorized to download this document.", "error")
        return redirect(url_for("documents.my_documents"))

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

