import pytest

from app import create_app, db
from app.auth.models import User
from app.audit.models import AuditLog
from app.audit.utils import log_audit_event, verify_audit_chain


@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "SECRET_KEY": "audit-test-secret",
    })

    with app.app_context():
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_audit_event_receives_sha256_hash(app):
    with app.app_context():
        event = log_audit_event(
            user_id=None,
            document_id=None,
            action="TEST_EVENT",
            details="Hash generation test",
        )

        assert event.event_hash is not None
        assert len(event.event_hash) == 64
        assert verify_audit_chain()["valid"] is True


def test_audit_events_link_to_previous_event(app):
    with app.app_context():
        first = log_audit_event(None, None, "FIRST_EVENT")
        second = log_audit_event(None, None, "SECOND_EVENT")

        assert second.previous_hash == first.event_hash
        assert second.event_hash != first.event_hash
        assert verify_audit_chain()["valid"] is True


def test_modified_audit_event_is_detected(app):
    with app.app_context():
        event = log_audit_event(
            None, None, "TEST_EVENT", "Original details"
        )

        event.details = "Modified details"
        db.session.commit()

        result = verify_audit_chain()

        assert result["valid"] is False
        assert result["broken_event_id"] == event.id


def test_admin_dashboard_displays_audit_integrity(client, app):
    client.post(
        "/register",
        data={
            "username": "auditadmin",
            "email": "auditadmin@example.com",
            "password": "TestPass123!",
        },
        follow_redirects=True,
    )

    with app.app_context():
        user = User.query.filter_by(username="auditadmin").first()
        user.role = "Administrator"
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": "auditadmin",
            "password": "TestPass123!",
        },
        follow_redirects=True,
    )

    response = client.get("/admin")

    assert response.status_code == 200
    assert b"Audit Trail Integrity" in response.data
    assert b"Valid" in response.data


def test_viewer_cannot_access_audit_integrity_dashboard(client):
    client.post(
        "/register",
        data={
            "username": "auditviewer",
            "email": "auditviewer@example.com",
            "password": "TestPass123!",
        },
        follow_redirects=True,
    )

    client.post(
        "/login",
        data={
            "username": "auditviewer",
            "password": "TestPass123!",
        },
        follow_redirects=True,
    )

    response = client.get("/admin")

    assert response.status_code == 403
