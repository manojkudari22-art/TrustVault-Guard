import os
from datetime import timezone

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


def format_system_time(value):
    if value is None:
        return "Unavailable"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone().strftime("%d %b %Y, %I:%M:%S %p")


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    database_uri = app.config["SQLALCHEMY_DATABASE_URI"]
    if database_uri.startswith("sqlite:///"):
        database_path = database_uri.replace("sqlite:///", "", 1)
        database_directory = os.path.dirname(database_path)
        if database_directory:
            os.makedirs(database_directory, exist_ok=True)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    app.add_template_filter(format_system_time, "system_time")

    login_manager.login_view = "auth.login"

    from app.auth.models import User
    from app.documents.models import Document
    from app.audit.models import AuditLog
    from app.documents.permissions import DocumentPermission

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    from app.auth.routes import auth
    from app.documents.routes import documents

    app.register_blueprint(auth)
    app.register_blueprint(documents)

    with app.app_context():
        db.create_all()

    return app
