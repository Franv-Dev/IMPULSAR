"""Tests del freno a la fuerza bruta en el login.

El escaneo dinamico entro 25 contrasenias erradas seguidas contra /auth/login
sin encontrar un solo limite, y la correcta paso en el intento 26. Lo mismo en
/auth/api/login. Estos tests son ese agujero, escrito para que no vuelva.

El contador vive en un diccionario de modulo (services/rate_limit.py); lo vacia
antes de cada test la fixture autouse `limite_de_login_limpio` de conftest.
"""

from config import TestingConfig
from db import db as _db
from main import create_app
from services import rate_limit


# --------------------------------------------------------------- el contador

def test_debajo_del_maximo_no_bloquea():
    for _ in range(4):
        rate_limit.registrar_fallo("k", ventana=900)

    assert rate_limit.segundos_de_bloqueo("k", maximo=5, bloqueo=600, ventana=900) == 0


def test_al_llegar_al_maximo_bloquea():
    for _ in range(5):
        rate_limit.registrar_fallo("k", ventana=900)

    espera = rate_limit.segundos_de_bloqueo("k", maximo=5, bloqueo=600, ventana=900)
    assert 0 < espera <= 601


def test_cada_clave_cuenta_por_su_cuenta():
    for _ in range(5):
        rate_limit.registrar_fallo("una", ventana=900)

    assert rate_limit.segundos_de_bloqueo("otra", maximo=5, bloqueo=600, ventana=900) == 0


def test_limpiar_borra_el_contador():
    for _ in range(5):
        rate_limit.registrar_fallo("k", ventana=900)
    rate_limit.limpiar("k")

    assert rate_limit.segundos_de_bloqueo("k", maximo=5, bloqueo=600, ventana=900) == 0


def test_los_fallos_viejos_no_cuentan(monkeypatch):
    """Cinco fallos sueltos a lo largo del dia no son cinco fallos seguidos."""
    reloj = [1000.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: reloj[0])

    for _ in range(4):
        rate_limit.registrar_fallo("k", ventana=900)
    # Pasa la ventana entera: lo anterior se olvida.
    reloj[0] += 1000
    rate_limit.registrar_fallo("k", ventana=900)

    assert rate_limit.segundos_de_bloqueo("k", maximo=5, bloqueo=600, ventana=900) == 0


def test_cumplido_el_bloqueo_se_arranca_de_cero(monkeypatch):
    """Y no con el contador al borde, que dejaria la cuenta muerta para siempre."""
    reloj = [1000.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: reloj[0])

    for _ in range(5):
        rate_limit.registrar_fallo("k", ventana=900)
    assert rate_limit.segundos_de_bloqueo("k", maximo=5, bloqueo=600, ventana=900) > 0

    reloj[0] += 601
    assert rate_limit.segundos_de_bloqueo("k", maximo=5, bloqueo=600, ventana=900) == 0

    # Un fallo mas no puede volver a bloquear enseguida: el contador quedo en 0.
    rate_limit.registrar_fallo("k", ventana=900)
    assert rate_limit.segundos_de_bloqueo("k", maximo=5, bloqueo=600, ventana=900) == 0


def test_el_diccionario_no_crece_sin_fin(monkeypatch):
    """Una fuerza bruta con IPs rotativas no puede comerse la memoria."""
    monkeypatch.setattr(rate_limit, "MAXIMO_DE_CLAVES", 50)

    for i in range(200):
        rate_limit.registrar_fallo(f"ip:{i}", ventana=900)

    assert len(rate_limit._fallos) <= 51


# --------------------------------------------------- /auth/login (formulario)

def _fallar_login(client, veces, username="tomy", password="mal"):
    ultima = None
    for _ in range(veces):
        ultima = client.post(
            "/auth/login", data={"username": username, "password": password}
        )
    return ultima


def test_el_login_se_bloquea_a_los_cinco_fallos(client, crear_usuario):
    """El agujero del escaneo, con los numeros de produccion."""
    crear_usuario(username="tomy", password="secreta123")

    # Los cinco primeros contestan que la contrasenia esta mal, no que se acabo.
    quinto = _fallar_login(client, 5)
    assert quinto.status_code == 200

    sexto = _fallar_login(client, 1)
    assert sexto.status_code == 429
    assert "Demasiados intentos" in sexto.get_data(as_text=True)
    assert int(sexto.headers["Retry-After"]) > 0


def test_bloqueado_ni_siquiera_entra_con_la_clave_correcta(client, crear_usuario):
    """Lo que hace que el freno sirva: el intento 26 del escaneo tambien cae."""
    crear_usuario(username="tomy", password="secreta123")

    _fallar_login(client, 5)

    respuesta = client.post(
        "/auth/login", data={"username": "tomy", "password": "secreta123"}
    )
    assert respuesta.status_code == 429
    with client.session_transaction() as sesion:
        assert "user_id" not in sesion


def test_cambiar_mayusculas_no_esquiva_el_bloqueo(client, crear_usuario):
    crear_usuario(username="tomy", password="secreta123")

    _fallar_login(client, 5, username="tomy")

    respuesta = client.post(
        "/auth/login", data={"username": "TOMY", "password": "mal"}
    )
    assert respuesta.status_code == 429


def test_un_login_bueno_borra_los_fallos(client, crear_usuario):
    """Cuatro errores y un acierto no dejan a nadie a un paso del bloqueo."""
    crear_usuario(username="tomy", password="secreta123")

    _fallar_login(client, 4)
    bueno = client.post(
        "/auth/login", data={"username": "tomy", "password": "secreta123"}
    )
    assert bueno.status_code == 302

    # Con el contador sin limpiar, el cuarto de esta tanda seria el bloqueo.
    cuarto = _fallar_login(client, 4)
    assert cuarto.status_code == 200


def test_el_bloqueo_de_una_cuenta_no_alcanza_a_otra(client, crear_usuario):
    crear_usuario(username="tomy", password="secreta123")
    crear_usuario(username="lucia", email="lucia@test.com", password="secreta123")

    _fallar_login(client, 5, username="tomy")

    otra = client.post(
        "/auth/login", data={"username": "lucia", "password": "secreta123"}
    )
    assert otra.status_code == 302


def test_una_cuenta_suspendida_no_se_bloquea_por_reintentar(client, crear_usuario, db):
    """La clave era la correcta: no hay nada que adivinar, no cuenta como fallo.

    Si contara, cualquiera que no entienda por que no entra se quedaria
    bloqueado ademas de suspendido, y el cartel dejaria de explicar el motivo.
    """
    usuario = crear_usuario(username="tomy", password="secreta123")
    usuario.is_banned = True
    db.session.commit()

    for _ in range(6):
        respuesta = client.post(
            "/auth/login", data={"username": "tomy", "password": "secreta123"}
        )

    assert respuesta.status_code == 200
    assert "suspendida" in respuesta.get_data(as_text=True)


def test_una_cuenta_suspendida_con_la_clave_mal_si_cuenta(client, crear_usuario, db):
    """El reves del anterior, y el que se escapaba.

    Una cuenta suspendida con la contrasenia MAL cae en "la contraseña es
    incorrecta" (el chequeo de baneo va despues), asi que si el perdon mirara
    is_banned en vez de la credencial, una cuenta baneada conocida serviria
    para probar claves sin gastar ningun contador.
    """
    usuario = crear_usuario(username="tomy", password="secreta123")
    usuario.is_banned = True
    db.session.commit()

    quinto = _fallar_login(client, 5)
    assert quinto.status_code == 200

    sexto = _fallar_login(client, 1)
    assert sexto.status_code == 429


# ----------------------------------------------------- /auth/api/login (JSON)

def test_la_api_tambien_se_bloquea(client, crear_usuario):
    """La otra puerta del escaneo, que estaba igual de abierta."""
    crear_usuario(username="tomy", email="tomy@test.com", password="secreta123")

    for _ in range(5):
        respuesta = client.post(
            "/auth/api/login", json={"email": "tomy@test.com", "password": "mal"}
        )
        assert respuesta.status_code == 401

    sexta = client.post(
        "/auth/api/login", json={"email": "tomy@test.com", "password": "mal"}
    )
    assert sexta.status_code == 429
    assert "Demasiados intentos" in sexta.get_json()["error"]
    assert int(sexta.headers["Retry-After"]) > 0


def test_la_api_bloqueada_tampoco_da_token(client, crear_usuario):
    crear_usuario(username="tomy", email="tomy@test.com", password="secreta123")

    for _ in range(5):
        client.post(
            "/auth/api/login", json={"email": "tomy@test.com", "password": "mal"}
        )

    respuesta = client.post(
        "/auth/api/login", json={"email": "tomy@test.com", "password": "secreta123"}
    )
    assert respuesta.status_code == 429
    assert "access_token" not in respuesta.get_json()


def test_el_limite_por_ip_cruza_las_dos_rutas(client, crear_usuario, app):
    """Gastar el cupo en la API no deja el formulario fresco.

    Es el limite flojo, el que atrapa el rociado: muchas cuentas distintas
    desde la misma direccion, sin llenar el contador de ninguna. Se baja a tres
    para no pagar veinte hashes en un test; los numeros reales los mira
    test_los_limites_de_produccion_son_los_de_config.
    """
    app.config["LOGIN_MAX_FALLOS_POR_IP"] = 3
    crear_usuario(username="tomy", password="secreta123")

    for i in range(3):
        client.post(
            "/auth/api/login", json={"email": f"nadie{i}@test.com", "password": "x"}
        )

    respuesta = client.post(
        "/auth/login", data={"username": "tomy", "password": "secreta123"}
    )
    assert respuesta.status_code == 429


def test_entrar_bien_no_limpia_el_contador_de_la_ip(client, crear_usuario, app):
    """Si lo limpiara, el limite por IP no existiria: bastaria con tener cuenta."""
    app.config["LOGIN_MAX_FALLOS_POR_IP"] = 3
    crear_usuario(username="tomy", password="secreta123")

    for i in range(2):
        client.post(
            "/auth/api/login", json={"email": f"nadie{i}@test.com", "password": "x"}
        )
    client.post("/auth/login", data={"username": "tomy", "password": "secreta123"})
    client.post("/auth/api/login", json={"email": "nadie9@test.com", "password": "x"})

    respuesta = client.post(
        "/auth/login", data={"username": "tomy", "password": "secreta123"}
    )
    assert respuesta.status_code == 429


# ------------------------------------- una sola cuenta, un solo contador
#
# Los tres de abajo son los agujeros que encontro la auditoria de la tanda: la
# clave de cuenta salia del texto que mandaba el cliente, asi que la misma
# persona podia tener mas de un contador y multiplicar sus intentos.

def test_alternar_formulario_y_api_no_duplica_el_contador(client, crear_usuario):
    """Medido en la auditoria: el primer 429 caia recien en el intento 11.

    El formulario manda el username y la API el email, asi que la misma
    persona generaba "login:cuenta:tomy" y "login:cuenta:tomy@test.com": dos
    contadores de cinco, o sea diez contrasenias erradas contra una cuenta.
    """
    crear_usuario(username="tomy", email="tomy@test.com", password="secreta123")

    codigos = []
    for _ in range(6):
        codigos.append(
            client.post(
                "/auth/login", data={"username": "tomy", "password": "mal"}
            ).status_code
        )
        codigos.append(
            client.post(
                "/auth/api/login", json={"email": "tomy@test.com", "password": "mal"}
            ).status_code
        )

    # Los cinco primeros fallos cuentan en la misma clave, venga por donde venga.
    assert 429 in codigos[:6], codigos
    assert codigos.count(429) >= 6, codigos


def test_gastar_el_cupo_en_la_api_bloquea_el_formulario(client, crear_usuario):
    crear_usuario(username="tomy", email="tomy@test.com", password="secreta123")

    for _ in range(5):
        client.post(
            "/auth/api/login", json={"email": "tomy@test.com", "password": "mal"}
        )

    respuesta = client.post(
        "/auth/login", data={"username": "tomy", "password": "secreta123"}
    )
    assert respuesta.status_code == 429


def test_las_tildes_no_regalan_cinco_intentos_mas(client, crear_usuario):
    """La collation de MySQL las ignora, asi que es el MISMO usuario.

    users.username vive en utf8mb4_unicode_ci: filter_by encuentra a
    "Panadería" buscando "Panaderia". Con .lower() a secas eran dos contadores
    distintos, y cada variante con o sin tilde daba otros cinco intentos.
    """
    crear_usuario(username="Panadería", password="secreta123")

    for _ in range(5):
        client.post("/auth/login", data={"username": "Panadería", "password": "mal"})

    # Mismo usuario escrito sin tilde: tiene que seguir bloqueado.
    respuesta = client.post(
        "/auth/login", data={"username": "Panaderia", "password": "mal"}
    )
    assert respuesta.status_code == 429


def test_un_usuario_que_no_existe_igual_cuenta(client):
    """Y sin tocar el contador de nadie real."""
    for _ in range(5):
        client.post("/auth/login", data={"username": "fantasma", "password": "mal"})

    respuesta = client.post(
        "/auth/login", data={"username": "fantasma", "password": "mal"}
    )
    assert respuesta.status_code == 429


def test_el_bloqueo_no_se_levanta_solo_si_la_ventana_es_corta(monkeypatch):
    """La invariante bloqueo <= ventana, sostenida por la funcion y no por config.

    _podar tira los fallos mas viejos que la ventana ANTES de mirar el bloqueo,
    asi que con una ventana mas corta que el bloqueo la espera se cortaba sola.
    Medido en la auditoria: bloqueo=60, ventana=1, decia 60 s y 1,2 s despues 0.
    """
    reloj = [1000.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: reloj[0])

    for _ in range(5):
        rate_limit.registrar_fallo("k", ventana=1)
    assert rate_limit.segundos_de_bloqueo("k", maximo=5, bloqueo=60, ventana=1) > 0

    reloj[0] += 2  # pasa la ventana, pero NO el bloqueo
    assert rate_limit.segundos_de_bloqueo("k", maximo=5, bloqueo=60, ventana=1) > 0

    reloj[0] += 60  # ahora si
    assert rate_limit.segundos_de_bloqueo("k", maximo=5, bloqueo=60, ventana=1) == 0


# ------------------------------------------------------------- detras del proxy

def test_sin_proxy_declarado_no_se_cree_el_x_forwarded_for(client, crear_usuario, app):
    """Si se lo creyera, cambiar la cabecera seria todo lo que hace falta.

    X-Forwarded-For lo escribe el cliente. Sin un proxy adelante que la pise,
    un atacante manda una direccion distinta por intento y el limite por IP
    deja de existir. Por eso PROXY_FIX_X_FOR arranca en cero.
    """
    app.config["LOGIN_MAX_FALLOS_POR_IP"] = 3

    for i in range(4):
        client.post(
            "/auth/api/login",
            json={"email": f"nadie{i}@test.com", "password": "x"},
            headers={"X-Forwarded-For": f"9.9.9.{i}"},
        )

    # Las cuatro contaron en la misma IP real, no en cuatro inventadas.
    respuesta = client.post(
        "/auth/api/login",
        json={"email": "otro@test.com", "password": "x"},
        headers={"X-Forwarded-For": "9.9.9.99"},
    )
    assert respuesta.status_code == 429


def test_con_proxy_declarado_cada_cliente_cuenta_aparte(monkeypatch):
    """Y detras de nginx, dos personas distintas no comparten el castigo.

    Sin esto, con la app publicada detras de un proxy remote_addr es siempre la
    del proxy: los veinte fallos pasarian a ser un limite global y bastaria un
    atacante para dejar afuera a todos.
    """
    monkeypatch.setattr(TestingConfig, "PROXY_FIX_X_FOR", 1)
    app = create_app("testing")
    app.config["LOGIN_MAX_FALLOS_POR_IP"] = 3
    cliente = app.test_client()

    with app.app_context():
        _db.create_all()
        try:
            for _ in range(4):
                cliente.post(
                    "/auth/api/login",
                    json={"email": "nadie@test.com", "password": "x"},
                    headers={"X-Forwarded-For": "9.9.9.1"},
                )

            # Otro cliente, otra direccion real: no arrastra el bloqueo del primero.
            respuesta = cliente.post(
                "/auth/api/login",
                json={"email": "otro@test.com", "password": "x"},
                headers={"X-Forwarded-For": "9.9.9.2"},
            )
            assert respuesta.status_code == 401
        finally:
            _db.session.remove()
            _db.drop_all()


def test_los_limites_de_produccion_son_los_de_config(app):
    """Los numeros que se prometieron, no los que un test bajo para correr rapido."""
    assert app.config["LOGIN_MAX_FALLOS_POR_CUENTA"] == 5
    assert app.config["LOGIN_MAX_FALLOS_POR_IP"] == 20
    assert app.config["LOGIN_BLOQUEO_SEGUNDOS"] == 600
    # La ventana tiene que ser mas larga que el bloqueo: si no, los fallos se
    # olvidan antes de que termine la pena y el bloqueo se levanta solo.
    assert app.config["LOGIN_VENTANA_SEGUNDOS"] > app.config["LOGIN_BLOQUEO_SEGUNDOS"]
