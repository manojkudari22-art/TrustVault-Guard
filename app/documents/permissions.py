from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
from app import db


class DocumentPermission(db.Model):
    __tablename__ = "document_permission"

    id = db.Column(db.Integer, primary_key=True)

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

    permission = db.Column(db.String(10), nullable=False)

    granted_by = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    revoked_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "user_id",
            name="uq_document_permission_user"
        ),
    )
