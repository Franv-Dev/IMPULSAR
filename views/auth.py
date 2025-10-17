from flask import (
    render_template, Blueprint, flash, request, session, url_for, redirect, g, jsonify
)
from models.user import User
from werkzeug.security import check_password_hash, generate_password_hash
from db import db
import functools

# --- JWT ---
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity
)
from datetime import timedelta

auth = Blueprint("auth", __name__, url_prefix="/auth")

# ============
#  VISTAS HTML (sesiones tradicionales)
# ============

@auth.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        rol = request.form.get("rol", "usuario").strip() or "usuario"
        email = request.form.get("email", "").strip()

        error = None

        if not username:
            error = "Se requiere nombre de usuario"
        elif not password:
            error = "Se requiere una contraseña"
        elif not email:
            error = "Se requiere un email"

        # Unicidad
        if error is None and User.query.filter_by(username=username).first():
            error = f"El usuario {username} ya se encuentra registrado"
        if error is None and User.query.filter_by(email=email).first():
            error = f"El email {email} ya se encuentra registrado"

        if error is None:
            user = User(
                username=username,
                email=email,
                password=generate_password_hash(password),  # guardamos HASH
                rol=rol
            )
            db.session.add(user)
            db.session.commit()
            flash("Registro exitoso. Iniciá sesión.")
            return redirect(url_for('auth.login'))

        flash(error)

    return render_template('auth/register.html')


@auth.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        error = None
        user = User.query.filter_by(username=username).first()

        if user is None:
            error = "El usuario es incorrecto"
        elif not check_password_hash(user.password, password):
            error = "La contraseña es incorrecta"

        if error is None:
            session.clear()
            session["user_id"] = user.id
            return redirect(url_for('blog.index'))

        flash(error)

    return render_template('auth/login.html')


@auth.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    g.user = User.query.get(user_id) if user_id else None


@auth.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('blog.index'))


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        return view(**kwargs)
    return wrapped_view


# ============
#  API JWT (JSON)  → /auth/api/...
# ============

@auth.post("/api/register")
def api_register():
    """Registro via JSON (devuelve usuario, sin token)."""
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    rol = (data.get("rol") or "usuario").strip() or "usuario"

    errors = []
    if not username: errors.append("username requerido")
    if not email: errors.append("email requerido")
    if not password: errors.append("password requerido")
    if User.query.filter_by(username=username).first(): errors.append("username ya existe")
    if User.query.filter_by(email=email).first(): errors.append("email ya existe")
    if errors:
        return jsonify({"errors": errors}), 400

    user = User(
        username=username,
        email=email,
        password=generate_password_hash(password),
        rol=rol
    )
    db.session.add(user)
    db.session.commit()
    return jsonify(user.serialize()), 201


@auth.post("/api/login")
def api_login():
    """Login via JSON → devuelve JWT."""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "email y password requeridos"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({"error": "credenciales inválidas"}), 401

    token = create_access_token(
        identity={"id": user.id, "rol": user.rol},
        expires_delta=timedelta(hours=1)
    )
    return jsonify({"access_token": token, "user": user.serialize()}), 200


@auth.get("/me")
@jwt_required()
def me():
    """Ver identidad extraída del token."""
    return jsonify({"current_user": get_jwt_identity()}), 200


# ============
#  Helpers de autorización por roles para usar en tus APIs
# ============

def role_required(*allowed_roles):
    """Usalo junto con @jwt_required() en endpoints JSON."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            ident = get_jwt_identity() or {}
            rol = ident.get("rol")
            if rol not in allowed_roles:
                return jsonify({"error": "No autorizado"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
