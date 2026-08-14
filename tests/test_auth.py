"""Tests de registro, login y autorizacion por roles."""

from flask import jsonify
from flask_jwt_extended import jwt_required
from werkzeug.security import check_password_hash, generate_password_hash

from models.user import Roles, User
from views.auth import role_required


# ------------------------------------------------------------------ unitarios

def test_password_hashing():
    plain = "mypassword"
    hashed = generate_password_hash(plain)
    assert check_password_hash(hashed, plain)
    assert not check_password_hash(hashed, "otra")


def test_la_contrasenia_nunca_se_guarda_en_texto_plano(client, db):
    client.post("/auth/api/register", json={
        "username": "user1",
        "email": "user1@test.com",
        "password": "secreta123",
    })

    user = User.query.filter_by(username="user1").first()
    assert user.password != "secreta123"
    assert check_password_hash(user.password, "secreta123")


def test_user_model_serialization(db):
    usertest = User(
        username="test",
        email="test100@gmail.com",
        password="test123",
        rol=Roles.ADMIN,
    )
    db.session.add(usertest)
    db.session.commit()

    data = usertest.serialize()
    assert data["username"] == "test"
    assert data["email"] == "test100@gmail.com"
    # La contrasenia no debe viajar nunca en la respuesta de la API.
    assert "password" not in data


def test_el_email_se_normaliza_a_minusculas(db):
    user = User(username="tomy", email="  Tomy@Ejemplo.COM ", password="x")
    db.session.add(user)
    db.session.commit()

    assert user.email == "tomy@ejemplo.com"


def test_el_rol_se_normaliza(db):
    user = User(username="tomy", email="t@t.com", password="x", rol="ADMIN")
    db.session.add(user)
    db.session.commit()

    assert user.rol == Roles.ADMIN


# ---------------------------------------------------------------- constraints

def test_no_se_pueden_repetir_usernames(client):
    primero = client.post("/auth/api/register", json={
        "username": "repetido", "email": "a@test.com", "password": "secreta123",
    })
    segundo = client.post("/auth/api/register", json={
        "username": "repetido", "email": "b@test.com", "password": "secreta123",
    })

    assert primero.status_code == 201
    assert segundo.status_code == 400


def test_no_se_pueden_repetir_emails_ni_cambiando_mayusculas(client):
    client.post("/auth/api/register", json={
        "username": "uno", "email": "mismo@test.com", "password": "secreta123",
    })
    resp = client.post("/auth/api/register", json={
        "username": "dos", "email": "MISMO@test.com", "password": "secreta123",
    })

    assert resp.status_code == 400


def test_no_se_puede_registrar_un_username_solo_numerico(client):
    """Daria un slug numerico, indistinguible de /perfil/<id>."""
    resp = client.post("/auth/api/register", json={
        "username": "12345", "email": "a@test.com", "password": "secreta123",
    })

    assert resp.status_code == 400


def test_el_registro_por_formulario_rechaza_un_username_numerico(client, db):
    from models.user import User

    client.post("/auth/register", data={
        "username": "999", "email": "a@test.com", "password": "secreta123",
    })

    assert User.query.filter_by(username="999").first() is None


# --------------------------------------------------------------------- roles

def test_role_required_rechaza_sin_token(client):
    app = client.application

    @app.route("/admin-test")
    @jwt_required()
    @role_required(Roles.ADMIN)
    def admin_test():
        return jsonify({"ok": True})

    assert client.get("/admin-test").status_code in (401, 403)


def test_role_required_rechaza_a_un_usuario_comun(client, crear_usuario):
    """Antes este caso rompia con AttributeError en vez de devolver 403."""
    app = client.application

    @app.route("/solo-admin")
    @jwt_required()
    @role_required(Roles.ADMIN)
    def solo_admin():
        return jsonify({"ok": True})

    crear_usuario(username="comun", email="comun@test.com", rol=Roles.USUARIO)
    token = client.post("/auth/api/login", json={
        "email": "comun@test.com", "password": "secreta123",
    }).get_json()["access_token"]

    resp = client.get("/solo-admin", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_role_required_deja_pasar_al_admin(client, crear_usuario):
    app = client.application

    @app.route("/tablero-admin")
    @jwt_required()
    @role_required(Roles.ADMIN)
    def tablero_admin():
        return jsonify({"ok": True})

    crear_usuario(username="jefa", email="jefa@test.com", rol=Roles.ADMIN)
    token = client.post("/auth/api/login", json={
        "email": "jefa@test.com", "password": "secreta123",
    }).get_json()["access_token"]

    resp = client.get("/tablero-admin", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True}


# ------------------------------------------------------------------ flujo API

def test_register_login_crud_flow(client):
    resp = client.post("/auth/api/register", json={
        "username": "user1",
        "email": "user1@test.com",
        "password": "secreta123",
    })
    assert resp.status_code == 201
    assert resp.get_json()["username"] == "user1"

    resp = client.post("/auth/api/login", json={
        "email": "user1@test.com",
        "password": "secreta123",
    })
    assert resp.status_code == 200
    token = resp.get_json()["access_token"]
    assert token

    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.get_json()["current_user"]["rol"] == Roles.USUARIO


def test_login_con_credenciales_incorrectas(client, crear_usuario):
    crear_usuario(username="tomy", email="tomy@test.com")

    resp = client.post("/auth/api/login", json={
        "email": "tomy@test.com", "password": "equivocada",
    })
    assert resp.status_code == 401


def test_login_por_formulario_inicia_sesion(client, crear_usuario):
    crear_usuario(username="tomy", email="tomy@test.com")

    resp = client.post(
        "/auth/login",
        data={"username": "tomy", "password": "secreta123"},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    with client.session_transaction() as sesion:
        assert sesion.get("user_id") is not None
