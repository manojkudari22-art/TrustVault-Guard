from datetime import datetime, timezone

from app import db


class DocumentEditRequest(db.Model):
    __tablename__ = "document_edit_request"

    id = db.Column(db.Integer, primary_key=True)

    document_id = db.Column(
        db.Integer,
        db.ForeignKey("document.id"),
        nullable=False,
        index=True
    )

    admin_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        index=True
    )

    owner_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        index=True
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="pending",
        index=True
    )

    requested_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    responded_at = db.Column(db.DateTime, nullable=True)

    document = db.relationship("Document")
    administrator = db.relationship("User", foreign_keys=[admin_id])
    owner = db.relationship("User", foreign_keys=[owner_id])
