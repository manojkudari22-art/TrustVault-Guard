from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from app.auth.models import User
from app import db
from app.documents.models import Document
from app.audit.utils import verify_audit_chain, log_audit_event

auth = Blueprint("auth", __name__)


@auth.route("/")
def home():
    return render_template("landing.html")



@auth.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "Viewer").strip()

        allowed_roles = {"Viewer", "Document Owner"}

        if role not in allowed_roles:
            flash("Invalid account type selected.")
            return redirect(url_for("auth.register"))

        if not username or not email or not password:
            flash("All fields are required.")
            return redirect(url_for("auth.register"))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.")
            return redirect(url_for("auth.register"))

        if User.query.filter_by(username=username).first():
            flash("Username already exists.")
            return redirect(url_for("auth.register"))

        if User.query.filter_by(email=email).first():
            flash("Email already exists.")
            return redirect(url_for("auth.register"))

        user = User(username=username, email=email, role=role)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash("Registration successful. Please log in.")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_identifier = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=login_identifier).first()

        if not user:
            user = User.query.filter_by(email=login_identifier.lower()).first()

        if user and user.is_active and user.check_password(password):
            login_user(user)
            return redirect(url_for("auth.dashboard"))

        flash("Invalid username or password.")

    return render_template("login.html")


@auth.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for("auth.login"))


def role_required(*roles):
    def decorator(view_function):
        @wraps(view_function)
        @login_required
        def wrapped_view(*args, **kwargs):
            if current_user.role not in roles:
                return "Forbidden", 403
            return view_function(*args, **kwargs)
        return wrapped_view
    return decorator


@auth.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@auth.route("/admin")
@role_required("Administrator")
def admin_dashboard():
    audit_integrity = verify_audit_chain()
    return render_template(
        "admin_dashboard.html",
        audit_integrity=audit_integrity
    )


@auth.route("/owner")
@role_required("Document Owner", "Administrator")
def owner_dashboard():
    document_count = Document.query.filter_by(owner_id=current_user.id).count()
    return render_template("owner_dashboard.html", document_count=document_count)

@auth.route("/history")
@login_required
def my_history():
    from sqlalchemy import or_
    from app.audit.models import AuditLog

    history_query = (
        db.session.query(AuditLog, User.username, Document.name)
        .outerjoin(User, AuditLog.user_id == User.id)
        .outerjoin(Document, AuditLog.document_id == Document.id)
    )

    if current_user.role == "Administrator":
        pass
    elif current_user.role == "Document Owner":
        history_query = history_query.filter(
            or_(
                AuditLog.user_id == current_user.id,
                Document.owner_id == current_user.id
            )
        )
    else:
        history_query = history_query.filter(
            AuditLog.user_id == current_user.id
        )

    history_entries = (
        history_query
        .order_by(AuditLog.timestamp.desc())
        .limit(200)
        .all()
    )

    return render_template(
        "history.html",
        history_entries=history_entries
    )

@auth.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not current_user.check_password(current_password):
            flash("Current password is incorrect.", "error")
        elif len(new_password) < 8:
            flash("New password must contain at least 8 characters.", "error")
        elif new_password != confirm_password:
            flash("New passwords do not match.", "error")
        elif current_user.check_password(new_password):
            flash("Choose a password different from your current password.", "error")
        else:
            current_user.set_password(new_password)

            try:
                log_audit_event(
                    current_user.id,
                    None,
                    "PASSWORD_CHANGED",
                    "Account password changed",
                    commit=False
                )
                db.session.commit()
            except Exception:
                db.session.rollback()
                raise

            flash("Password changed successfully.", "success")
            return redirect(url_for("auth.settings"))

    return render_template("settings.html")

@auth.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        current_password = request.form.get("current_password", "")

        if not username or not email:
            flash("Username and email are required.", "error")
        elif len(username) > 80 or len(email) > 120:
            flash("Username or email exceeds the allowed length.", "error")
        elif "@" not in email:
            flash("Enter a valid email address.", "error")
        elif not current_user.check_password(current_password):
            flash("Current password is incorrect.", "error")
        elif User.query.filter(User.username == username, User.id != current_user.id).first():
            flash("Username already exists.", "error")
        elif User.query.filter(User.email == email, User.id != current_user.id).first():
            flash("Email already exists.", "error")
        elif username == current_user.username and email == current_user.email:
            flash("No profile changes detected.", "error")
        else:
            current_user.username = username
            current_user.email = email

            try:
                log_audit_event(
                    current_user.id,
                    None,
                    "PROFILE_UPDATED",
                    "Account profile information updated",
                    commit=False
                )
                db.session.commit()
            except Exception:
                db.session.rollback()
                raise

            flash("Profile updated successfully.", "success")
            return redirect(url_for("auth.profile"))

    return render_template("profile.html")
