from flask import (
    render_template, Blueprint, flash, request, session, url_for, redirect, g, jsonify, abort
)
from models.user import Roles, User
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy.exc import IntegrityError
from db import db
from services.validation import validate_password
import functools

# --- JWT ---
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity, get_jwt
)

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
        # Se normaliza a minusculas para que Tomy@x.com y tomy@x.com sean el
        # mismo usuario, tanto al registrar como al consultar unicidad.
        email = request.form.get("email", "").strip().lower()

        error = None

        if not username:
            error = "Se requiere nombre de usuario"
        elif not password:
            error = "Se requiere una contraseña"
        elif not email:
            error = "Se requiere un email"
        else:
            error = validate_password(password)

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
            try:
                db.session.commit()
            except IntegrityError:
                # Los chequeos de unicidad de arriba tienen una ventana de
                # carrera: entre el SELECT y el INSERT puede entrar otro
                # registro igual. La base de datos es la que decide.
                db.session.rollback()
                error = "Ese usuario o email ya está registrado."
            else:
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
        elif user.is_banned:
            error = "Esta cuenta fue suspendida. Contactate con soporte."

        if error is None:
            session.clear()
            session["user_id"] = user.id
            return redirect(url_for('index'))

        flash(error)

    return render_template('auth/login.html')


@auth.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    g.user = User.query.get(user_id) if user_id else None


@auth.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        return view(**kwargs)
    return wrapped_view


def admin_required(view):
    """Para vistas HTML (sesion), analogo a role_required(Roles.ADMIN) de la API."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        if g.user.rol != Roles.ADMIN:
            abort(403)
        return view(**kwargs)
    return wrapped_view



#  API JWT (JSON)


@auth.post("/api/register")
def api_register():
    """Registro via JSON (devuelve usuario, sin token)."""
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    rol = (data.get("rol") or "usuario").strip() or "usuario"

    errors = []
    if not username: errors.append("username requerido")
    if not email: errors.append("email requerido")
    if not password:
        errors.append("password requerido")
    else:
        password_error = validate_password(password)
        if password_error:
            errors.append(password_error)
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
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"errors": ["username o email ya existe"]}), 409
    return jsonify(user.serialize()), 201


@auth.post("/api/login")
def api_login():
    """Login via JSON → devuelve JWT."""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "email y password requeridos"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({"error": "credenciales inválidas"}), 401
    if user.is_banned:
        return jsonify({"error": "Esta cuenta fue suspendida."}), 403

    # La duracion sale de JWT_ACCESS_TOKEN_EXPIRES en config.py, asi se puede
    # ajustar por entorno sin tocar el codigo.
    token = create_access_token(
        identity=str(user.id),
        additional_claims={"rol": user.rol},
    )
    return jsonify({"access_token": token, "user": user.serialize()}), 200



@auth.get("/me")
@jwt_required()
def me():
    # La identity siempre es el id del usuario como string (ver api_login).
    user_id = get_jwt_identity()

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404

    return jsonify({"current_user": user.serialize()}), 200




#  Helpers de autorización por roles para usar en tus APIs


def role_required(*allowed_roles):
    """Usalo junto con @jwt_required() en endpoints JSON.

    El rol viaja en los *claims adicionales* del token (ver api_login), no en
    la identity. Por eso se lee con get_jwt(), que devuelve el payload completo
    del JWT; get_jwt_identity() devuelve solo el id del usuario (un string).
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            claims = get_jwt() or {}
            rol = claims.get("rol")
            if rol not in allowed_roles:
                return jsonify({"error": "No autorizado"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
