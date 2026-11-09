import io
import zipfile
from pathlib import Path

import pytest

from app import create_app, db
from app.audit.models import AuditLog
from app.auth.models import User
from app.documents.models import Document
from app.documents.permissions import DocumentPermission


@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "SECRET_KEY": "sharing-test-secret",
        "UPLOAD_FOLDER": str(tmp_path),
    })

    with app.app_context():
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def register_user(client, username):
    return client.post(
        "/register",
        data={
            "username": username,
            "email": f"{username}@example.com",
            "password": "TestPass123!",
        },
        follow_redirects=True,
    )


def login_user(client, username):
    return client.post(
        "/login",
        data={
            "username": username,
            "password": "TestPass123!",
        },
        follow_redirects=True,
    )


def create_document(
    app,
    owner_username,
    recipient_username=None,
    permission="view",
    active=True,
):
    stored_filename = f"{owner_username}-test.pdf"
    file_content = b"TrustVault security test document"

    with app.app_context():
        owner = User.query.filter_by(username=owner_username).first()
        owner.role = "Document Owner"

        document = Document(
            name="Security Test Report",
            original_filename="report.pdf",
            stored_filename=stored_filename,
            category="Reports",
            owner_id=owner.id,
        )
        db.session.add(document)
        db.session.flush()

        if recipient_username:
            recipient = User.query.filter_by(
                username=recipient_username
            ).first()

            db.session.add(DocumentPermission(
                document_id=document.id,
                user_id=recipient.id,
                permission=permission,
                granted_by=owner.id,
                is_active=active,
            ))

        db.session.commit()
        document_id = document.id

    Path(app.config["UPLOAD_FOLDER"], stored_filename).write_bytes(
        file_content
    )

    return document_id, file_content


def test_active_shared_document_is_visible(client, app):
    register_user(client, "shareowner")
    register_user(client, "shareviewer")

    create_document(
        app, "shareowner", "shareviewer", permission="view"
    )

    login_user(client, "shareviewer")
    response = client.get("/documents/shared-with-me")

    assert response.status_code == 200
    assert b"Security Test Report" in response.data
    assert b"view access" in response.data


def test_revoked_shared_document_is_not_visible(client, app):
    register_user(client, "revokeowner")
    register_user(client, "revokeviewer")

    create_document(
        app, "revokeowner", "revokeviewer",
        permission="view", active=False
    )

    login_user(client, "revokeviewer")
    response = client.get("/documents/shared-with-me")

    assert response.status_code == 200
    assert b"Security Test Report" not in response.data


def test_document_owner_can_preview(client, app):
    register_user(client, "previewowner")

    document_id, file_content = create_document(
        app, "previewowner"
    )

    login_user(client, "previewowner")
    response = client.get(f"/documents/view/{document_id}")

    assert response.status_code == 200
    assert response.data == file_content


def test_view_permission_can_preview_but_cannot_download(client, app):
    register_user(client, "viewowner")
    register_user(client, "viewrecipient")

    document_id, file_content = create_document(
        app, "viewowner", "viewrecipient", permission="view"
    )

    login_user(client, "viewrecipient")

    preview = client.get(f"/documents/view/{document_id}")
    download = client.get(
        f"/documents/download/{document_id}",
        follow_redirects=False
    )

    assert preview.status_code == 200
    assert preview.data == file_content
    assert download.status_code == 302


def test_download_permission_can_download(client, app):
    register_user(client, "downloadowner")
    register_user(client, "downloadrecipient")

    document_id, file_content = create_document(
        app, "downloadowner", "downloadrecipient",
        permission="download"
    )

    login_user(client, "downloadrecipient")
    response = client.get(f"/documents/download/{document_id}")

    assert response.status_code == 200
    assert response.data == file_content


def test_unauthorized_user_cannot_preview_or_download(client, app):
    register_user(client, "privateowner")
    register_user(client, "outsider")

    document_id, _ = create_document(
        app, "privateowner"
    )

    login_user(client, "outsider")

    preview = client.get(
        f"/documents/view/{document_id}",
        follow_redirects=False
    )
    download = client.get(
        f"/documents/download/{document_id}",
        follow_redirects=False
    )

    assert preview.status_code == 302
    assert download.status_code == 302


def test_revoked_recipient_cannot_preview_or_download(client, app):
    register_user(client, "revokedowner")
    register_user(client, "revokedrecipient")

    document_id, _ = create_document(
        app, "revokedowner", "revokedrecipient",
        permission="download", active=False
    )

    login_user(client, "revokedrecipient")

    preview = client.get(
        f"/documents/view/{document_id}",
        follow_redirects=False
    )
    download = client.get(
        f"/documents/download/{document_id}",
        follow_redirects=False
    )

    assert preview.status_code == 302
    assert download.status_code == 302

def test_document_owner_can_edit_metadata(client, app):
    register_user(client, "editowner")
    document_id, _ = create_document(app, "editowner")

    login_user(client, "editowner")

    response = client.post(
        f"/documents/edit/{document_id}",
        data={"name": "Updated Report", "category": "Finance"},
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        document = db.session.get(Document, document_id)
        assert document.name == "Updated Report"
        assert document.category == "Finance"


def test_unauthorized_user_cannot_edit_or_delete(client, app):
    register_user(client, "secureowner")
    register_user(client, "secureoutsider")

    document_id, _ = create_document(app, "secureowner")

    login_user(client, "secureoutsider")

    edit_response = client.post(
        f"/documents/edit/{document_id}",
        data={"name": "Hacked", "category": "Hacked"},
    )

    delete_response = client.post(
        f"/documents/delete/{document_id}",
    )

    assert edit_response.status_code == 302
    assert delete_response.status_code == 302

    with app.app_context():
        document = db.session.get(Document, document_id)
        assert document.name == "Security Test Report"
        assert document.deleted_at is None


def test_owner_can_soft_delete_and_revoke_sharing(client, app):
    register_user(client, "deleteowner")
    register_user(client, "deleterecipient")

    document_id, _ = create_document(
        app, "deleteowner", "deleterecipient",
        permission="download"
    )

    login_user(client, "deleteowner")

    response = client.post(
        f"/documents/delete/{document_id}",
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        document = db.session.get(Document, document_id)
        permission = DocumentPermission.query.filter_by(
            document_id=document_id,
            user_id=User.query.filter_by(
                username="deleterecipient"
            ).first().id,
        ).first()

        assert document.deleted_at is not None
        assert permission.is_active is False

        from app.audit.models import AuditLog
        from app.audit.utils import verify_audit_chain

        event = AuditLog.query.filter_by(
            document_id=document_id,
            action="DOCUMENT_DELETE",
        ).first()

        assert event is not None
        assert verify_audit_chain()["valid"] is True

    assert not Path(
        app.config["UPLOAD_FOLDER"],
        "deleteowner-test.pdf"
    ).exists()


def test_deleted_document_cannot_be_previewed_or_downloaded(client, app):
    register_user(client, "deletedowner")

    document_id, _ = create_document(app, "deletedowner")

    login_user(client, "deletedowner")

    delete_response = client.post(
        f"/documents/delete/{document_id}",
    )
    assert delete_response.status_code == 302

    preview = client.get(
        f"/documents/view/{document_id}",
        follow_redirects=False,
    )
    download = client.get(
        f"/documents/download/{document_id}",
        follow_redirects=False,
    )

    assert preview.status_code == 404
    assert download.status_code == 302


def test_document_owner_can_replace_content(client, app):
    register_user(client, "replaceowner")
    document_id, old_content = create_document(app, "replaceowner")
    login_user(client, "replaceowner")

    response = client.post(
        f"/documents/replace/{document_id}",
        data={
            "file": (
                io.BytesIO(b"%PDF-1.7\nNew owner replacement content"),
                "replacement.pdf",
                "application/pdf",
            )
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        document = db.session.get(Document, document_id)
        assert document.name == "Security Test Report"
        assert document.original_filename == "replacement.pdf"
        new_filename = document.stored_filename

        event = AuditLog.query.filter_by(
            document_id=document_id,
            action="DOCUMENT_CONTENT_REPLACED",
        ).first()
        assert event is not None

    new_path = Path(app.config["UPLOAD_FOLDER"], new_filename)
    old_path = Path(
        app.config["UPLOAD_FOLDER"],
        "replaceowner-test.pdf",
    )

    assert new_path.read_bytes() == b"%PDF-1.7\nNew owner replacement content"
    assert not old_path.exists()


def test_edit_permission_user_can_replace_content(client, app):
    register_user(client, "replaceowner2")
    register_user(client, "replaceeditor")

    document_id, _ = create_document(
        app,
        "replaceowner2",
        "replaceeditor",
        permission="edit",
    )

    login_user(client, "replaceeditor")

    response = client.post(
        f"/documents/replace/{document_id}",
        data={
            "file": (
                io.BytesIO(b"%PDF-1.7\nEditor replacement content"),
                "editor-replacement.pdf",
                "application/pdf",
            )
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        document = db.session.get(Document, document_id)
        assert document.name == "Security Test Report"
        assert document.original_filename == "editor-replacement.pdf"
        new_filename = document.stored_filename

        event = AuditLog.query.filter_by(
            document_id=document_id,
            action="DOCUMENT_CONTENT_REPLACED",
        ).first()
        assert event is not None
        assert event.user_id == User.query.filter_by(
            username="replaceeditor"
        ).first().id

    new_path = Path(app.config["UPLOAD_FOLDER"], new_filename)
    assert new_path.read_bytes() == b"%PDF-1.7\nEditor replacement content"


@pytest.mark.parametrize(
    ("permission", "active"),
    [
        ("view", True),
        ("download", True),
        ("edit", False),
    ],
)
def test_users_without_active_edit_permission_cannot_replace_content(
    client, app, permission, active
):
    register_user(client, "deniedreplaceowner")
    register_user(client, "deniedreplaceuser")

    document_id, old_content = create_document(
        app,
        "deniedreplaceowner",
        "deniedreplaceuser",
        permission=permission,
        active=active,
    )

    login_user(client, "deniedreplaceuser")

    response = client.post(
        f"/documents/replace/{document_id}",
        data={
            "file": (
                io.BytesIO(b"Unauthorized replacement"),
                "attack.pdf",
                "application/pdf",
            )
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        document = db.session.get(Document, document_id)
        assert document.stored_filename == "deniedreplaceowner-test.pdf"

        event = AuditLog.query.filter_by(
            document_id=document_id,
            action="ACCESS_DENIED",
        ).first()
        assert event is not None

    old_path = Path(
        app.config["UPLOAD_FOLDER"],
        "deniedreplaceowner-test.pdf",
    )
    assert old_path.read_bytes() == old_content
    assert not Path(
        app.config["UPLOAD_FOLDER"],
        "attack.pdf",
    ).exists()


def test_replacement_rejects_disallowed_file_type(client, app):
    register_user(client, "invalidreplaceowner")
    document_id, old_content = create_document(
        app, "invalidreplaceowner"
    )

    login_user(client, "invalidreplaceowner")

    response = client.post(
        f"/documents/replace/{document_id}",
        data={
            "file": (
                io.BytesIO(b"Executable content"),
                "malware.exe",
                "application/octet-stream",
            )
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        document = db.session.get(Document, document_id)
        assert document.stored_filename == "invalidreplaceowner-test.pdf"

    old_path = Path(
        app.config["UPLOAD_FOLDER"],
        "invalidreplaceowner-test.pdf",
    )
    assert old_path.read_bytes() == old_content



def test_replacement_rejects_spoofed_pdf_signature(client, app):
    register_user(client, "spoofedpdfowner")
    document_id, old_content = create_document(
        app, "spoofedpdfowner"
    )

    login_user(client, "spoofedpdfowner")

    response = client.post(
        f"/documents/replace/{document_id}",
        data={
            "file": (
                io.BytesIO(b"This is not a real PDF file"),
                "fake.pdf",
                "application/pdf",
            )
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        document = db.session.get(Document, document_id)
        assert document.stored_filename == "spoofedpdfowner-test.pdf"
        assert document.original_filename == "report.pdf"

    old_path = Path(
        app.config["UPLOAD_FOLDER"],
        "spoofedpdfowner-test.pdf",
    )
    assert old_path.read_bytes() == old_content


def test_replacement_rejects_invalid_docx_archive(client, app):
    register_user(client, "invaliddocxowner")
    document_id, old_content = create_document(
        app, "invaliddocxowner"
    )

    login_user(client, "invaliddocxowner")

    response = client.post(
        f"/documents/replace/{document_id}",
        data={
            "file": (
                io.BytesIO(b"This is not a valid DOCX archive"),
                "fake.docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        document = db.session.get(Document, document_id)
        assert document.stored_filename == "invaliddocxowner-test.pdf"
        assert document.original_filename == "report.pdf"

    old_path = Path(
        app.config["UPLOAD_FOLDER"],
        "invaliddocxowner-test.pdf",
    )
    assert old_path.read_bytes() == old_content


def test_replacement_rejects_docx_path_traversal(client, app):
    register_user(client, "docxpathowner")
    document_id, old_content = create_document(
        app, "docxpathowner"
    )

    login_user(client, "docxpathowner")

    malicious_docx = io.BytesIO()

    with zipfile.ZipFile(malicious_docx, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>',
        )
        archive.writestr(
            "word/document.xml",
            '<document xmlns="http://schemas.openxmlformats.org/wordprocessingml/2006/main"></document>',
        )
        archive.writestr("../evil.txt", "malicious content")

    malicious_docx.seek(0)

    response = client.post(
        f"/documents/replace/{document_id}",
        data={
            "file": (
                malicious_docx,
                "malicious.docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        document = db.session.get(Document, document_id)
        assert document.stored_filename == "docxpathowner-test.pdf"
        assert document.original_filename == "report.pdf"

    old_path = Path(
        app.config["UPLOAD_FOLDER"],
        "docxpathowner-test.pdf",
    )
    assert old_path.read_bytes() == old_content



def test_file_type_upload_size_limits():
    from app.documents.routes import MAX_FILE_SIZES

    expected_limits = {
        "pdf": 25 * 1024 * 1024,
        "doc": 15 * 1024 * 1024,
        "docx": 20 * 1024 * 1024,
        "txt": 5 * 1024 * 1024,
        "pptx": 20 * 1024 * 1024,
        "xlsx": 20 * 1024 * 1024,
        "csv": 10 * 1024 * 1024,
    }

    assert MAX_FILE_SIZES == expected_limits


def test_oversized_pdf_is_rejected():
    from app.documents.routes import MAX_FILE_SIZES, allowed_file

    oversized_content = io.BytesIO(
        b"x" * (MAX_FILE_SIZES["pdf"] + 1)
    )

    assert not allowed_file(
        "large.pdf",
        "application/pdf",
        oversized_content,
    )

def create_test_ooxml_file(extension):
    from app.documents.routes import ALLOWED_EXTENSIONS

    main_parts = {
        "pptx": (
            "ppt/presentation.xml",
            b'<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>',
        ),
        "xlsx": (
            "xl/workbook.xml",
            b'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>',
        ),
    }

    main_path, main_xml = main_parts[extension]

    content_types = (
        b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        b'<Default Extension="xml" ContentType="application/xml"/>'
        b'</Types>'
    )

    file_stream = io.BytesIO()

    with zipfile.ZipFile(file_stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr(main_path, main_xml)

    file_stream.seek(0)
    return file_stream


@pytest.mark.parametrize(
    ("extension", "mimetype"),
    [
        ("pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ],
)
def test_valid_ooxml_upload_validation(extension, mimetype):
    from app.documents.routes import allowed_file

    file_stream = create_test_ooxml_file(extension)

    assert allowed_file(
        f"sample.{extension}",
        mimetype,
        file_stream,
    )


def test_valid_csv_upload_validation():
    from app.documents.routes import allowed_file

    content = b"name,department\nManoj,CSE\nRavi,IT\n"

    assert allowed_file(
        "students.csv",
        "text/csv",
        io.BytesIO(content),
    )


@pytest.mark.parametrize(
    ("filename", "mimetype", "content"),
    [
        (
            "fake.pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            b"not a zip archive",
        ),
        (
            "fake.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            b"not a zip archive",
        ),
        (
            "fake.csv",
            "text/csv",
            b"name,\xff\xfe",
        ),
        (
            "fake.csv",
            "text/csv",
            b"name\x00,value",
        ),
    ],
)
def test_invalid_new_file_formats_are_rejected(
    filename, mimetype, content
):
    from app.documents.routes import allowed_file

    assert not allowed_file(
        filename,
        mimetype,
        io.BytesIO(content),
    )


@pytest.mark.parametrize(
    ("extension", "mimetype"),
    [
        ("pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ],
)
def test_ooxml_wrong_internal_structure_is_rejected(extension, mimetype):
    from app.documents.routes import allowed_file

    file_stream = io.BytesIO()

    with zipfile.ZipFile(file_stream, "w") as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("wrong/document.xml", b"<document/>")

    file_stream.seek(0)

    assert not allowed_file(
        f"wrong.{extension}",
        mimetype,
        file_stream,
    )


def test_ooxml_path_traversal_is_rejected():
    from app.documents.routes import allowed_file

    file_stream = create_test_ooxml_file("pptx")

    original = file_stream.getvalue()
    malicious_stream = io.BytesIO()

    with zipfile.ZipFile(malicious_stream, "w") as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("ppt/presentation.xml", b"<presentation/>")
        archive.writestr("../outside.txt", original)

    malicious_stream.seek(0)

    assert not allowed_file(
        "malicious.pptx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        malicious_stream,
    )


def test_csv_wrong_mimetype_is_rejected():
    from app.documents.routes import allowed_file

    assert not allowed_file(
        "students.csv",
        "application/pdf",
        io.BytesIO(b"name,department\nManoj,CSE\n"),
    )


def create_text_document(app, owner_username, content, filename="notes.txt",
                         recipient_username=None, permission="view",
                         active=True):
    stored_filename = f"{owner_username}-editor-test.txt"

    with app.app_context():
        owner = User.query.filter_by(username=owner_username).first()
        owner.role = "Document Owner"

        document = Document(
            name="Editor Test",
            original_filename=filename,
            stored_filename=stored_filename,
            category="General",
            owner_id=owner.id,
        )
        db.session.add(document)
        db.session.flush()

        if recipient_username:
            recipient = User.query.filter_by(
                username=recipient_username
            ).first()
            db.session.add(DocumentPermission(
                document_id=document.id,
                user_id=recipient.id,
                permission=permission,
                granted_by=owner.id,
                is_active=active,
            ))

        db.session.commit()
        document_id = document.id

    Path(app.config["UPLOAD_FOLDER"], stored_filename).write_bytes(content)
    return document_id, stored_filename


def test_document_owner_can_edit_txt_content(client, app):
    register_user(client, "editorowner")
    document_id, old_filename = create_text_document(
        app, "editorowner", b"Original text"
    )
    login_user(client, "editorowner")

    page = client.get(f"/documents/edit-content/{document_id}")
    assert page.status_code == 200

    response = client.post(
        f"/documents/edit-content/{document_id}",
        data={"content": "Updated text content"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        document = db.session.get(Document, document_id)
        new_filename = document.stored_filename
        event = AuditLog.query.filter_by(
            document_id=document_id,
            action="DOCUMENT_CONTENT_EDITED",
        ).first()

        assert event is not None
        assert event.user_id == User.query.filter_by(
            username="editorowner"
        ).first().id

    assert Path(app.config["UPLOAD_FOLDER"], new_filename).read_bytes() == (
        b"Updated text content"
    )
    assert not Path(app.config["UPLOAD_FOLDER"], old_filename).exists()


def test_viewer_with_edit_permission_can_edit_txt(client, app):
    register_user(client, "contentowner")
    register_user(client, "contenteditor")

    document_id, _ = create_text_document(
        app,
        "contentowner",
        b"Before edit",
        recipient_username="contenteditor",
        permission="edit",
    )
    login_user(client, "contenteditor")

    response = client.post(
        f"/documents/edit-content/{document_id}",
        data={"content": "Edited by permitted viewer"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        document = db.session.get(Document, document_id)
        content = Path(
            app.config["UPLOAD_FOLDER"], document.stored_filename
        ).read_bytes()
        event = AuditLog.query.filter_by(
            document_id=document_id,
            action="DOCUMENT_CONTENT_EDITED",
        ).first()

    assert content == b"Edited by permitted viewer"
    assert event is not None


@pytest.mark.parametrize(
    ("permission", "active"),
    [
        ("view", True),
        ("download", True),
        ("edit", False),
    ],
)
def test_viewer_without_active_edit_permission_cannot_edit_txt(
    client, app, permission, active
):
    register_user(client, "contentdenyowner")
    register_user(client, "contentdenyuser")

    document_id, stored_filename = create_text_document(
        app,
        "contentdenyowner",
        b"Original protected content",
        recipient_username="contentdenyuser",
        permission=permission,
        active=active,
    )
    login_user(client, "contentdenyuser")

    response = client.post(
        f"/documents/edit-content/{document_id}",
        data={"content": "Unauthorized change"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    assert Path(
        app.config["UPLOAD_FOLDER"], stored_filename
    ).read_bytes() == b"Original protected content"

    with app.app_context():
        event = AuditLog.query.filter_by(
            document_id=document_id,
            action="ACCESS_DENIED",
        ).first()
        assert event is not None


def test_editor_allows_empty_txt_content(client, app):
    register_user(client, "emptytextowner")
    document_id, _ = create_text_document(
        app, "emptytextowner", b"Text to clear"
    )
    login_user(client, "emptytextowner")

    response = client.post(
        f"/documents/edit-content/{document_id}",
        data={"content": ""},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        document = db.session.get(Document, document_id)
        new_filename = document.stored_filename

    assert Path(app.config["UPLOAD_FOLDER"], new_filename).read_bytes() == b""


def test_editor_rejects_nul_byte_content(client, app):
    register_user(client, "nultextowner")
    document_id, stored_filename = create_text_document(
        app, "nultextowner", b"Original safe content"
    )
    login_user(client, "nultextowner")

    response = client.post(
        f"/documents/edit-content/{document_id}",
        data={"content": "bad\x00content"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    assert Path(
        app.config["UPLOAD_FOLDER"], stored_filename
    ).read_bytes() == b"Original safe content"


def test_editor_rejects_invalid_csv_content(client, app):
    register_user(client, "csvcontentowner")
    document_id, stored_filename = create_text_document(
        app,
        "csvcontentowner",
        b"name,age\nAlice,20\n",
        filename="people.csv",
    )
    login_user(client, "csvcontentowner")

    response = client.post(
        f"/documents/edit-content/{document_id}",
        data={"content": 'name,age\n"Alice,20\n'},
        follow_redirects=True,
    )
    assert response.status_code == 200

    assert Path(
        app.config["UPLOAD_FOLDER"], stored_filename
    ).read_bytes() == b"name,age\nAlice,20\n"


def test_editor_audit_failure_preserves_original_file(
    client, app, monkeypatch
):
    register_user(client, "auditfailureowner")
    document_id, old_filename = create_text_document(
        app, "auditfailureowner", b"Original content survives"
    )
    login_user(client, "auditfailureowner")

    from app.documents import routes as document_routes

    def fail_audit(*args, **kwargs):
        raise RuntimeError("Simulated audit failure")

    monkeypatch.setattr(document_routes, "log_audit_event", fail_audit)

    response = client.post(
        f"/documents/edit-content/{document_id}",
        data={"content": "This must not replace the original"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        document = db.session.get(Document, document_id)
        assert document.stored_filename == old_filename

    upload_folder = Path(app.config["UPLOAD_FOLDER"])
    assert (upload_folder / old_filename).read_bytes() == (
        b"Original content survives"
    )
    assert len(list(upload_folder.glob("*.txt"))) == 1

@pytest.mark.parametrize("endpoint", ["view", "download"])
def test_document_routes_reject_path_traversal(client, app, tmp_path, endpoint):
    register_user(client, "pathowner")

    document_id, _ = create_document(app, "pathowner")

    outside_file = tmp_path.parent / "outside.pdf"
    outside_file.write_bytes(b"Sensitive file outside upload folder")

    with app.app_context():
        document = db.session.get(Document, document_id)
        document.stored_filename = "../outside.pdf"
        db.session.commit()

    login_user(client, "pathowner")
    response = client.get(f"/documents/{endpoint}/{document_id}")

    assert response.status_code == 302
    assert b"Sensitive file outside upload folder" not in response.data

@pytest.mark.parametrize("method", ["get", "post"])
def test_editor_rejects_path_traversal(client, app, method):
    register_user(client, "editorpathowner")
    document_id, _ = create_document(app, "editorpathowner")

    with app.app_context():
        document = db.session.get(Document, document_id)
        document.stored_filename = "../outside.pdf"
        db.session.commit()

    login_user(client, "editorpathowner")

    response = getattr(client, method)(
        f"/documents/edit-content/{document_id}",
        data={"content": "Unauthorized file access"} if method == "post" else None,
    )

    assert response.status_code == 302

def test_replacement_rejects_stored_filename_path_traversal(client, app, tmp_path):
    register_user(client, "replacepathowner")
    document_id, original_content = create_document(app, "replacepathowner")

    outside_file = tmp_path.parent / "outside.pdf"
    outside_file.write_bytes(b"Sensitive file outside upload folder")

    with app.app_context():
        document = db.session.get(Document, document_id)
        document.stored_filename = "../outside.pdf"
        db.session.commit()

    login_user(client, "replacepathowner")

    response = client.post(
        f"/documents/replace/{document_id}",
        data={
            "file": (io.BytesIO(b"%PDF-1.7 replacement"), "replacement.pdf")
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert outside_file.read_bytes() == b"Sensitive file outside upload folder"

    with app.app_context():
        document = db.session.get(Document, document_id)
        assert document.stored_filename == "../outside.pdf"
