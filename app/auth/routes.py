from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from app.auth.models import User
from app import db
from app.documents.models import Document

auth = Blueprint("auth", __name__)


@auth.route("/")
def home():
    return redirect(url_for("auth.login"))



@auth.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("All fields are required.")
            return redirect(url_for("auth.register"))

        if User.query.filter_by(username=username).first():
            flash("Username already exists.")
            return redirect(url_for("auth.register"))

        if User.query.filter_by(email=email).first():
            flash("Email already exists.")
            return redirect(url_for("auth.register"))

        user = User(username=username, email=email, role="Viewer")
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


@auth.route("/logout")
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
    return render_template("admin_dashboard.html")


@auth.route("/owner")
@role_required("Document Owner", "Administrator")
def owner_dashboard():
    document_count = Document.query.filter_by(owner_id=current_user.id).count()
    return render_template("owner_dashboard.html", document_count=document_count)
