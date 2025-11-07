import pytest
from flask import Flask
from flask_jwt_extended import JWTManager,jwt_required,create_access_token
from werkzeug.security import check_password_hash, generate_password_hash
from models.user import User
from views.auth import auth
from db import db
from main import app
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# ========================================
# FIXTURE de aplicación Flask de prueba
# ========================================
@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test_secret"
    app.config["JWT_SECRET_KEY"] = "jwt_secret_test"
    db.init_app(app)
    jwt = JWTManager(app)

    app.register_blueprint(auth)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()


# TESTS UNITARIOS


def test_password_hashing():
    """Verifica que el hash de la contraseña se genera y valida correctamente."""
    plain = "mypassword"
    hashed = generate_password_hash(plain)
    assert check_password_hash(hashed, plain)
    assert not check_password_hash(hashed, "otra")

def test_user_model_serialization(app):
    """Valida que el modelo User se serializa correctamente."""
    usertest = User(username="test", email="test100@gmail.com", password="test123", rol="admin")
    db.session.add(usertest)
    db.session.commit()
    data = usertest.serialize()
    assert "username" in data
    assert data["email"] == "test100@gmail.com"

def test_role_required_unauthorized(client):
    """Test simple de lógica: rol no autorizado devuelve 403."""
    from views.auth import role_required
    from flask import jsonify

    app = client.application


    @app.route("/admin-test")
    @jwt_required()
    @role_required("admin")
    def admin_test():
        return jsonify({"ok": True})

    # No hay JWT → debería devolver 403 porque get_jwt_identity() = None
    response = client.get("/admin-test")
    assert response.status_code in (401,403)

# ========================================
# TEST DE INTEGRACIÓN COMPLETO
# ========================================

def test_register_login_crud_flow(client):
    #  Registro
    resp = client.post("/auth/api/register", json={
        "username": "user1",
        "email": "user1@test.com",
        "password": "1234"
    })
    assert resp.status_code == 201
    user_data = resp.get_json()
    assert user_data["username"] == "user1"

    #  Login
    resp = client.post("/auth/api/login", json={
        "email": "user1@test.com",
        "password": "1234"
    })
    assert resp.status_code == 200
    login_data = resp.get_json()
    token = login_data["access_token"]
    assert token is not None

    #  Operación protegida 
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/auth/me", headers=headers)
    assert resp.status_code == 200
    current = resp.get_json()["current_user"]
    assert current["rol"] == "usuario"

