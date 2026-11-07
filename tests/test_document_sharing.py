from pathlib import Path

import pytest

from app import create_app, db
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

