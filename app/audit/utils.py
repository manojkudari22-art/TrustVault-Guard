from app import db
from app.audit.models import AuditLog


def log_audit_event(user_id, document_id, action, details=None):
    event = AuditLog(
        user_id=user_id,
        document_id=document_id,
        action=action,
        details=details
    )

    db.session.add(event)
    db.session.commit()
