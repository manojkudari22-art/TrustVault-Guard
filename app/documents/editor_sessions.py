from datetime import datetime, timezone

from app import db


class DocumentEditorSession(db.Model):
    __tablename__ = "document_editor_session"

    id = db.Column(db.Integer, primary_key=True)

    document_key = db.Column(db.String(64), nullable=True, unique=True, index=True)

    session_key = db.Column(
        db.String(64),
        nullable=False,
        unique=True,
        index=True
    )

    document_id = db.Column(
        db.Integer,
        db.ForeignKey("document.id"),
        nullable=False,
        index=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        index=True
    )

    original_stored_filename = db.Column(
        db.String(255),
        nullable=False
    )

    last_saved_filename = db.Column(
        db.String(255),
        nullable=False
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="active",
        index=True
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    expires_at = db.Column(
        db.DateTime,
        nullable=False,
        index=True
    )

    last_saved_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)

    document = db.relationship("Document")
    user = db.relationship("User")

