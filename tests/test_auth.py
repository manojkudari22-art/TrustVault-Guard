import pytest

from app import create_app, db
from app.auth.models import User


@pytest.fixture
def app():
    app = create_app()
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SECRET_KEY="test-secret-key",
    )

    with app.app_context():
        db.drop_all()
        db.create_all()
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
    response = client.get("/logout", follow_redirects=True)
    assert response.status_code == 200
