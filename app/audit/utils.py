import hashlib
import json
from datetime import datetime, timezone

from app import db
from app.audit.models import AuditLog


def _event_payload(event):
    return {
        "id": event.id,
        "user_id": event.user_id,
        "document_id": event.document_id,
        "action": event.action,
        "details": event.details,
        "timestamp": event.timestamp.isoformat(timespec="microseconds"),
        "previous_hash": event.previous_hash,
    }


def _calculate_hash(event):
    payload = json.dumps(
        _event_payload(event),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def log_audit_event(user_id, document_id, action, details=None, commit=True):
    chain_status = verify_audit_chain()

    if not chain_status["valid"]:
        raise RuntimeError(
            f"Cannot append audit event: {chain_status['message']}"
        )

    previous_event = (
        AuditLog.query
        .order_by(AuditLog.id.desc())
        .first()
    )

    previous_hash = previous_event.event_hash if previous_event else None

    event = AuditLog(
        user_id=user_id,
        document_id=document_id,
        action=action,
        details=details,
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
        previous_hash=previous_hash,
    )

    try:
        db.session.add(event)
        db.session.flush()

        event.event_hash = _calculate_hash(event)

        if commit:
            db.session.commit()
        return event

    except Exception:
        db.session.rollback()
        raise


def verify_audit_chain():
    events = (
        AuditLog.query
        .order_by(AuditLog.id.asc())
        .all()
    )

    previous_hash = None

    for event in events:
        if not event.event_hash:
            return {
                "valid": False,
                "total": len(events),
                "broken_event_id": event.id,
                "message": "Audit event hash is missing",
            }

        if event.previous_hash != previous_hash:
            return {
                "valid": False,
                "total": len(events),
                "broken_event_id": event.id,
                "message": "Previous hash mismatch",
            }

        expected_hash = _calculate_hash(event)

        if event.event_hash != expected_hash:
            return {
                "valid": False,
                "total": len(events),
                "broken_event_id": event.id,
                "message": "Event content or hash was modified",
            }

        previous_hash = event.event_hash

    return {
        "valid": True,
        "total": len(events),
        "broken_event_id": None,
        "message": "Audit hash chain is valid",
    }
