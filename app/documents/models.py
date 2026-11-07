from datetime import datetime, timezone

from app import db


class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(255), nullable=False)

    original_filename = db.Column(
        db.String(255),
        nullable=False
    )

    stored_filename = db.Column(
        db.String(255),
        unique=True,
        nullable=False
    )

    category = db.Column(
        db.String(100),
        nullable=False,
        default="General"
    )

    owner_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        index=True
    )

    uploaded_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    owner = db.relationship(
        "User",
        backref=db.backref("documents", lazy=True)
    )

    deleted_at = db.Column(db.DateTime, nullable=True)
