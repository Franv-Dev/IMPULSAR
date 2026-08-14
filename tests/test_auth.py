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


def test_no_se_pueden_repetir_usernames_cambiando_mayusculas_o_tildes(client):
    """En MySQL el unique usa utf8mb4_unicode_ci: "Panadería" y "panaderia" son
    el mismo username y el INSERT explotaba con IntegrityError. SQLite si los
    distingue, asi que sin el chequeo normalizado este caso no se detecta."""
    primero = client.post("/auth/api/register", json={
        "username": "Panadería", "email": "a@test.com", "password": "secreta123",
    })
    segundo = client.post("/auth/api/register", json={
        "username": "panaderia", "email": "b@test.com", "password": "secreta123",
    })

    assert primero.status_code == 201
    assert segundo.status_code == 400
    assert "username ya existe" in segundo.get_json()["errors"]


def test_la_colision_de_username_tambien_la_agarra_el_formulario(client, db):
    from models.user import User

    client.post("/auth/register", data={
        "username": "Ñandú", "email": "a@test.com", "password": "secreta123",
    })
    respuesta = client.post("/auth/register", data={
        "username": "nandu", "email": "b@test.com", "password": "secreta123",
    })

    assert respuesta.status_code == 200  # se queda en el formulario
    assert User.query.count() == 1


def test_dos_usernames_realmente_distintos_no_se_bloquean(client):
    """La normalizacion no debe pasarse de celosa: la collation tampoco ignora
    espacios ni puntuacion."""
    primero = client.post("/auth/api/register", json={
        "username": "pan casero", "email": "a@test.com", "password": "secreta123",
    })
    segundo = client.post("/auth/api/register", json={
        "username": "pan-casero", "email": "b@test.com", "password": "secreta123",
    })

    assert primero.status_code == 201
    assert segundo.status_code == 201


def test_normalizar_username_replica_la_collation_de_mysql():
    from services.validation import normalizar_username

    # Iguales para MySQL (verificado con SELECT 'a' = 'b' en utf8mb4_unicode_ci)
    for a, b in (("Panadería", "panaderia"), ("Ñandú", "nandu"),
                 ("Tomy", "tomy"), ("café", "cafe"), ("ß", "ss")):
        assert normalizar_username(a) == normalizar_username(b), (a, b)

    # Distintos para MySQL: no se deben colapsar
    for a, b in (("a b", "a  b"), ("a-b", "a b")):
        assert normalizar_username(a) != normalizar_username(b), (a, b)

    # Dos nombres en otro alfabeto siguen siendo distintos entre si: descartar
    # todo lo no-ASCII los dejaria vacios a los dos y los haria colisionar.
    assert normalizar_username("Привет") != normalizar_username("Пока")


def test_no_se_puede_registrar_un_username_mas_largo_que_la_columna(client):
    """Sin validar el largo, el nombre llegaba al INSERT y MySQL tiraba un
    DataError sin manejar: 500 en vez de un error de formulario."""
    from services.validation import MAX_USERNAME_LENGTH

    resp = client.post("/auth/api/register", json={
        "username": "a" * (MAX_USERNAME_LENGTH + 1),
        "email": "largo@test.com",
        "password": "secreta123",
    })

    assert resp.status_code == 400
    assert any("50" in e for e in resp.get_json()["errors"])


def test_un_username_del_largo_maximo_si_se_puede_registrar(client):
    from services.validation import MAX_USERNAME_LENGTH

    resp = client.post("/auth/api/register", json={
        "username": "a" * MAX_USERNAME_LENGTH,
        "email": "justo@test.com",
        "password": "secreta123",
    })

    assert resp.status_code == 201


def test_el_registro_por_formulario_rechaza_un_username_largo(client, db):
    from models.user import User
    from services.validation import MAX_USERNAME_LENGTH

    demasiado_largo = "a" * (MAX_USERNAME_LENGTH + 10)
    respuesta = client.post("/auth/register", data={
        "username": demasiado_largo, "email": "largo@test.com", "password": "secreta123",
    })

    assert respuesta.status_code == 200  # vuelve al formulario, no revienta
    assert User.query.filter_by(username=demasiado_largo).first() is None


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
