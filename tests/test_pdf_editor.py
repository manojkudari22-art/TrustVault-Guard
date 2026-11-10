import io
from pathlib import Path

import pytest
import pymupdf

from app import create_app, db
from app.auth.models import User
from app.audit.models import AuditLog
from app.documents.models import Document
from app.documents.edit_requests import DocumentEditRequest


@pytest.fixture
def app(tmp_path):
    application = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "SECRET_KEY": "pdf-editor-test-secret",
        "UPLOAD_FOLDER": str(tmp_path),
    })

    with application.app_context():
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def register_user(client, username):
    response = client.post(
        "/register",
        data={
            "username": username,
            "email": f"{username}@example.com",
            "password": "TestPass123!",
        },
        follow_redirects=True,
    )
    return response


def login_user(client, username):
    return client.post(
        "/login",
        data={
            "username": username,
            "password": "TestPass123!",
        },
        follow_redirects=True,
    )


def create_valid_pdf():
    pdf = pymupdf.open()
    page = pdf.new_page(width=595, height=842)
    page.insert_text((60, 80), "TrustVault PDF integration test")
    content = pdf.tobytes()
    pdf.close()
    return content


def prepare_users_and_document(client, app, prefix):
    owner_name = f"{prefix}owner"
    viewer_name = f"{prefix}viewer"
    admin_name = f"{prefix}admin"

    register_user(client, owner_name)
    register_user(client, viewer_name)
    register_user(client, admin_name)

    pdf_content = create_valid_pdf()
    filename = f"{prefix}-original.pdf"

    with app.app_context():
        owner = User.query.filter_by(username=owner_name).first()
        viewer = User.query.filter_by(username=viewer_name).first()
        admin = User.query.filter_by(username=admin_name).first()

        owner.role = "Document Owner"
        viewer.role = "Viewer"
        admin.role = "Administrator"

        document = Document(
            name="PDF Integration Test",
            original_filename="integration-test.pdf",
            stored_filename=filename,
            category="Testing",
            owner_id=owner.id,
        )

        db.session.add(document)
        db.session.commit()
        document_id = document.id

    Path(app.config["UPLOAD_FOLDER"], filename).write_bytes(pdf_content)

    return {
        "owner": owner_name,
        "viewer": viewer_name,
        "admin": admin_name,
        "document_id": document_id,
        "filename": filename,
        "pdf_content": pdf_content,
    }


def test_owner_can_preview_and_save_all_pdf_annotations(client, app):
    data = prepare_users_and_document(client, app, "pdfsave")

    login_user(client, data["owner"])

    editor = client.get(
        f"/documents/edit-pdf/{data['document_id']}"
    )
    preview = client.get(
        f"/documents/pdf-page/{data['document_id']}/0"
    )

    assert editor.status_code == 200
    assert b"PDF Editor" in editor.data
    assert preview.status_code == 200
    assert preview.content_type.startswith("image/png")

    with app.app_context():
        document = db.session.get(Document, data["document_id"])
        original_version = document.stored_filename

    response = client.post(
        f"/documents/edit-pdf/{data['document_id']}/save",
        json={
            "version": original_version,
            "operations": [
                {
                    "type": "text",
                    "page": 0,
                    "x": 0.15,
                    "y": 0.15,
                    "text": "Owner added text",
                    "font_size": 12,
                },
                {
                    "type": "highlight",
                    "page": 0,
                    "x": 0.15,
                    "y": 0.30,
                    "width": 0.35,
                    "height": 0.04,
                },
                {
                    "type": "draw",
                    "page": 0,
                    "points": [
                        [0.15, 0.50],
                        [0.25, 0.52],
                        [0.35, 0.50],
                    ],
                },
            ],
        },
    )

    assert response.status_code == 200
    result = response.get_json()
    assert result["success"] is True
    assert result["version"] != original_version

    new_path = Path(app.config["UPLOAD_FOLDER"], result["version"])
    assert new_path.is_file()

    with pymupdf.open(str(new_path)) as pdf:
        annotation_types = {
            annotation.type[1]
            for annotation in pdf[0].annots()
        }

    assert {"FreeText", "Highlight", "Ink"}.issubset(annotation_types)

    with app.app_context():
        document = db.session.get(Document, data["document_id"])
        assert document.stored_filename == result["version"]

        assert not Path(
            app.config["UPLOAD_FOLDER"], original_version
        ).exists()

        event = AuditLog.query.filter_by(
            document_id=data["document_id"],
            action="DOCUMENT_PDF_ANNOTATED",
        ).first()

        assert event is not None
        assert '"annotation_count": 3' in event.details


def test_viewer_cannot_preview_or_save_pdf(client, app):
    data = prepare_users_and_document(client=client, app=app, prefix="pdfview")

    login_user(client, data["viewer"])

    preview = client.get(
        f"/documents/pdf-page/{data['document_id']}/0"
    )
    save = client.post(
        f"/documents/edit-pdf/{data['document_id']}/save",
        json={
            "version": data["filename"],
            "operations": [
                {
                    "type": "text",
                    "page": 0,
                    "x": 0.2,
                    "y": 0.2,
                    "text": "Unauthorized",
                }
            ],
        },
    )

    assert preview.status_code == 403
    assert save.status_code == 403

    with app.app_context():
        document = db.session.get(Document, data["document_id"])
        assert document.stored_filename == data["filename"]

        denied_events = AuditLog.query.filter_by(
            document_id=data["document_id"],
            action="ACCESS_DENIED",
        ).count()

        assert denied_events >= 1


def test_admin_requires_owner_approval_before_pdf_edit(client, app):
    data = prepare_users_and_document(client, app, "pdfadmin")

    login_user(client, data["admin"])

    denied = client.post(
        f"/documents/edit-pdf/{data['document_id']}/save",
        json={
            "version": data["filename"],
            "operations": [
                {
                    "type": "text",
                    "page": 0,
                    "x": 0.2,
                    "y": 0.2,
                    "text": "Admin edit",
                }
            ],
        },
    )

    assert denied.status_code == 403

    with app.app_context():
        admin = User.query.filter_by(username=data["admin"]).first()
        owner = User.query.filter_by(username=data["owner"]).first()

        request_record = DocumentEditRequest(
            document_id=data["document_id"],
            admin_id=admin.id,
            owner_id=owner.id,
            status="approved",
        )
        db.session.add(request_record)
        db.session.commit()

    approved_preview = client.get(
        f"/documents/pdf-page/{data['document_id']}/0"
    )
    assert approved_preview.status_code == 200

    approved_save = client.post(
        f"/documents/edit-pdf/{data['document_id']}/save",
        json={
            "version": data["filename"],
            "operations": [
                {
                    "type": "text",
                    "page": 0,
                    "x": 0.2,
                    "y": 0.2,
                    "text": "Approved admin edit",
                }
            ],
        },
    )

    assert approved_save.status_code == 200


def test_stale_pdf_version_cannot_overwrite_newer_version(client, app):
    data = prepare_users_and_document(client, app, "pdfstale")

    login_user(client, data["owner"])

    first_save = client.post(
        f"/documents/edit-pdf/{data['document_id']}/save",
        json={
            "version": data["filename"],
            "operations": [
                {
                    "type": "text",
                    "page": 0,
                    "x": 0.2,
                    "y": 0.2,
                    "text": "First version",
                }
            ],
        },
    )

    assert first_save.status_code == 200
    latest_version = first_save.get_json()["version"]

    stale_save = client.post(
        f"/documents/edit-pdf/{data['document_id']}/save",
        json={
            "version": data["filename"],
            "operations": [
                {
                    "type": "text",
                    "page": 0,
                    "x": 0.3,
                    "y": 0.3,
                    "text": "Stale edit",
                }
            ],
        },
    )

    assert stale_save.status_code == 409

    with app.app_context():
        document = db.session.get(Document, data["document_id"])
        assert document.stored_filename == latest_version


def test_invalid_pdf_annotation_does_not_replace_original(client, app):
    data = prepare_users_and_document(client, app, "pdfinvalid")

    login_user(client, data["owner"])

    response = client.post(
        f"/documents/edit-pdf/{data['document_id']}/save",
        json={
            "version": data["filename"],
            "operations": [
                {
                    "type": "text",
                    "page": 99,
                    "x": 0.2,
                    "y": 0.2,
                    "text": "Invalid page",
                }
            ],
        },
    )

    assert response.status_code == 400

    with app.app_context():
        document = db.session.get(Document, data["document_id"])
        assert document.stored_filename == data["filename"]

        original_path = Path(
            app.config["UPLOAD_FOLDER"], data["filename"]
        )
        assert original_path.is_file()
        assert original_path.read_bytes() == data["pdf_content"]




@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("x", True),
        ("y", True),
        ("font_size", True),
    ],
)
def test_pdf_text_annotation_rejects_boolean_coordinates_and_font(
    client, app, field, value
):
    data = prepare_users_and_document(client, app, f"pdfbool{field}")
    login_user(client, data["owner"])

    operation = {
        "type": "text",
        "page": 0,
        "x": 0.2,
        "y": 0.2,
        "text": "Boolean validation test",
        "font_size": 12,
    }
    operation[field] = value

    response = client.post(
        f"/documents/edit-pdf/{data['document_id']}/save",
        json={
            "version": data["filename"],
            "operations": [operation],
        },
    )

    assert response.status_code == 400

    with app.app_context():
        document = db.session.get(Document, data["document_id"])
        assert document.stored_filename == data["filename"]

