from flask import Blueprint, request, session, jsonify, g
from models.user import User
from werkzeug.security import check_password_hash, generate_password_hash
from db import db
import functools
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity
)
from datetime import timedelta

auth = Blueprint("auth", __name__, url_prefix="/auth")


# ===========================
#   REGISTRO (JSON)
# ===========================
@auth.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    email = (data.get("email") or "").strip()
    rol = (data.get("rol") or "usuario").strip() or "usuario"

    errors = []
    if not username:
        errors.append("Se requiere nombre de usuario")
    if not password:
        errors.append("Se requiere contraseña")
    if not email:
        errors.append("Se requiere email")

    if User.query.filter_by(username=username).first():
        errors.append(f"El usuario {username} ya existe")
    if User.query.filter_by(email=email).first():
        errors.append(f"El email {email} ya está registrado")

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

    return jsonify({
        "message": "Registro exitoso",
        "user": user.serialize()
    }), 201


# ===========================
#   LOGIN (JSON)
# ===========================
@auth.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Se requiere usuario y contraseña"}), 400

    user = User.query.filter_by(username=username).first()

    if user is None:
        return jsonify({"error": "Usuario incorrecto"}), 401
    if not check_password_hash(user.password, password):
        return jsonify({"error": "Contraseña incorrecta"}), 401

    # Creamos token JWT
    token = create_access_token(
        identity={"id": user.id, "rol": user.rol},
        expires_delta=timedelta(hours=1)
    )

    return jsonify({
        "message": "Inicio de sesión exitoso",
        "access_token": token,
        "user": user.serialize()
    }), 200


# ===========================
#   LOGOUT (JSON)
# ===========================
@auth.route('/logout', methods=["POST"])
@jwt_required()
def logout():
    # En JWT, el logout es opcional (solo en frontend se descarta el token)
    return jsonify({"message": "Sesión cerrada exitosamente"}), 200


# ===========================
#   OBTENER USUARIO LOGUEADO
# ===========================
@auth.get("/me")
@jwt_required()
def me():
    """Devuelve datos del usuario actual."""
    ident = get_jwt_identity()
    user = User.query.get(ident["id"])
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404
    return jsonify(user.serialize()), 200


# ===========================
#   DECORADOR login_required (JSON)
# ===========================
def login_required(view):
    @functools.wraps(view)
    @jwt_required()
    def wrapped_view(**kwargs):
        return view(**kwargs)
    return wrapped_view


# ===========================
#   REQUERIR ROL
# ===========================
def role_required(*allowed_roles):
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
