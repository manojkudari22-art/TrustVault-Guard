import pytest

from app import create_app, db
from app.auth.models import User


@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "SECRET_KEY": "test-secret-key",
    })

    with app.app_context():
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()


def register(client, username="testuser", email="test@example.com",
             password="TestPass123!"):
    return client.post(
        "/register",
        data={
            "username": username,
            "email": email,
            "password": password,
        },
        follow_redirects=True,
    )


def login(client, username="testuser", password="TestPass123!"):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def test_registration_assigns_viewer_role(client, app):
    register(client)

    with app.app_context():
        user = User.query.filter_by(username="testuser").first()
        assert user.role == "Viewer"
        assert user.check_password("TestPass123!")


def test_login_success(client):
    register(client)
    response = login(client)
    assert response.status_code == 200
    assert b"Welcome" in response.data


def test_viewer_can_access_dashboard(client):
    register(client)
    login(client)
    response = client.get("/dashboard")
    assert response.status_code == 200


def test_viewer_cannot_access_admin_dashboard(client):
    register(client)
    login(client)
    response = client.get("/admin")
    assert response.status_code == 403


def test_admin_can_access_admin_dashboard(client, app):
    register(client)

    with app.app_context():
        user = User.query.filter_by(username="testuser").first()
        user.role = "Administrator"
        db.session.commit()

    login(client)
    response = client.get("/admin")
    assert response.status_code == 200


def test_owner_can_access_owner_dashboard(client, app):
    register(client)

    with app.app_context():
        user = User.query.filter_by(username="testuser").first()
        user.role = "Document Owner"
        db.session.commit()

    login(client)
    response = client.get("/owner")
    assert response.status_code == 200


def test_viewer_cannot_access_owner_dashboard(client):
    register(client)
    login(client)
    response = client.get("/owner")
    assert response.status_code == 403


def test_logout(client):
    register(client)
    login(client)
    response = client.post("/logout", follow_redirects=True)
    assert response.status_code == 200

def test_viewer_can_access_settings(client):
    register(client)
    login(client)

    response = client.get("/settings")

    assert response.status_code == 200
    assert b"Account Settings" in response.data
    assert b"Change Password" in response.data


def test_viewer_can_change_password(client, app):
    register(client)
    login(client)

    response = client.post(
        "/settings",
        data={
            "current_password": "TestPass123!",
            "new_password": "NewPass123!",
            "confirm_password": "NewPass123!",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        user = User.query.filter_by(username="testuser").first()
        assert user.check_password("NewPass123!")


def test_password_change_rejects_wrong_current_password(client, app):
    register(client)
    login(client)

    client.post(
        "/settings",
        data={
            "current_password": "WrongPassword!",
            "new_password": "NewPass123!",
            "confirm_password": "NewPass123!",
        },
        follow_redirects=True,
    )

    with app.app_context():
        user = User.query.filter_by(username="testuser").first()
        assert user.check_password("TestPass123!")
        assert not user.check_password("NewPass123!")


def test_password_change_creates_audit_event(client, app):
    from app.audit.models import AuditLog

    register(client)
    login(client)

    client.post(
        "/settings",
        data={
            "current_password": "TestPass123!",
            "new_password": "NewPass123!",
            "confirm_password": "NewPass123!",
        },
        follow_redirects=True,
    )

    with app.app_context():
        event = AuditLog.query.filter_by(
            action="PASSWORD_CHANGED"
        ).first()

        assert event is not None
        assert event.details == "Account password changed"

def test_logout_requires_post(client):
    response = client.get("/logout")
    assert response.status_code == 405


def test_logout_post_ends_session(client):
    client.post(
        "/register",
        data={
            "username": "logoutuser",
            "email": "logoutuser@example.com",
            "password": "TestPass123!",
        },
        follow_redirects=True,
    )

    client.post(
        "/login",
        data={
            "username": "logoutuser",
            "password": "TestPass123!",
        },
        follow_redirects=True,
    )

    response = client.post("/logout", follow_redirects=True)

    assert response.status_code == 200
    assert b"You have been logged out." in response.data
    assert client.get("/settings").status_code == 302

def test_password_change_rolls_back_when_audit_fails(client, app, monkeypatch):
    import app.auth.routes as auth_routes
    from app.audit.models import AuditLog

    register(client)
    login(client)

    def fail_audit(*args, **kwargs):
        raise RuntimeError("Simulated audit failure")

    monkeypatch.setattr(auth_routes, "log_audit_event", fail_audit)

    with pytest.raises(RuntimeError, match="Simulated audit failure"):
        client.post(
            "/settings",
            data={
                "current_password": "TestPass123!",
                "new_password": "NewPass123!",
                "confirm_password": "NewPass123!",
            },
        )

    with app.app_context():
        user = User.query.filter_by(username="testuser").first()
        assert user.check_password("TestPass123!")
        assert not user.check_password("NewPass123!")

        event = AuditLog.query.filter_by(action="PASSWORD_CHANGED").first()
        assert event is None

def test_registration_rejects_short_password(client, app):
    response = register(
        client,
        username="shortpass",
        email="shortpass@example.com",
        password="Short1!",
    )

    assert b"Password must contain at least 8 characters." in response.data

    with app.app_context():
        user = User.query.filter_by(username="shortpass").first()
        assert user is None
