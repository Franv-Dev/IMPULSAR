from flask import (
    render_template, Blueprint, current_app, flash, request, session, url_for,
    redirect, g, jsonify, abort
)
from models.user import Roles, User
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy.exc import IntegrityError
from db import db
from services import rate_limit
from services.validation import (
    normalizar_username, validate_email, validate_password, validate_username,
)
import functools

# --- JWT ---
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity, get_jwt
)

auth = Blueprint("auth", __name__, url_prefix="/auth")

# Los unicos roles que alguien puede pedir para si mismo al registrarse.
#
# Roles.ADMIN NO esta, y esa es la razon de que exista esta constante: el
# formulario tenia un <select> con "Administrador" adentro y la vista guardaba
# lo que viniera, asi que cualquiera se registraba como admin (y por la API,
# mandando {"rol": "admin"}, sin siquiera pasar por el formulario). Sacarlo del
# HTML no alcanza: el que decide es el servidor.
#
# Administrador es un permiso que se otorga, no una opcion que se elige. Hoy se
# asigna a mano en la base; cuando exista el panel para darlo, va por ahi.
ROLES_AL_REGISTRARSE = (Roles.USUARIO, Roles.EMPRENDEDOR)


def _rol_pedido(valor):
    """El rol que se guarda, a partir de lo que mando el cliente.

    Cualquier cosa que no sea uno de los dos permitidos cae en USUARIO, que es
    el que menos puede: ante un valor raro se elige el menor privilegio, no el
    mayor, y tampoco se corta con un error porque el rol es opcional.
    """
    normalizado = (valor or "").strip().lower()
    return normalizado if normalizado in ROLES_AL_REGISTRARSE else Roles.USUARIO


# ------------------------------------------- freno a la fuerza bruta del login
#
# El escaneo de seguridad entro veinticinco contrasenias erradas seguidas sin
# encontrar un solo freno, y la correcta paso en el intento veintiseis. Lo que
# sigue es ese freno. Vive aca y no dentro de cada vista porque las dos puertas
# (formulario y API) tienen que contar en el mismo lugar; los numeros salen de
# config.py, que es donde estan explicados.
#
# Se cuentan DOS claves por intento, y alcanza con que una este bloqueada:
#
#   cuenta:<username o email>   el ataque de siempre, muchas claves contra una
#                               persona
#   ip:<direccion>              el rociado, una clave comun contra muchas
#                               personas, que nunca llena el contador de
#                               ninguna cuenta
#
# La clave de IP la comparten las dos rutas a proposito: si no, un atacante
# gastaria su cupo en /auth/login y seguiria fresco en /auth/api/login.


def _claves_del_intento(usuario, identificador):
    """Devuelve (claves_de_cuenta, clave_de_ip) para un intento de login.

    SON DOS CLAVES DE CUENTA Y NO UNA, y cada una tapa un agujero distinto que
    la otra deja abierto. Las dos se cuentan a la vez y alcanza con que
    cualquiera este bloqueada.

      - POR ID DEL USUARIO. El formulario manda el username y la API el email:
        con la clave sacada del texto, la misma persona tenia dos contadores y
        alternando las dos puertas entraban diez contrasenias erradas en vez de
        cinco (medido: el primer 429 caia en el intento 11). El id es el mismo
        venga por donde venga. Solo existe si el usuario existe.

      - POR TEXTO NORMALIZADO. Cubre al usuario que no existe -- que igual hay
        que contar -- y ademas no depende de la collation de la base. En MySQL
        (utf8mb4_unicode_ci) "Panaderia" y "Panadería" son el mismo usuario y
        los dos caen en la clave de id; en SQLite el filter_by es exacto, no
        encuentra a nadie con la variante y sin esta clave cada forma de
        escribir el nombre regalaria otros cinco intentos. normalizar_username
        pliega mayusculas y tildes igual que el registro.
    """
    claves = []
    if usuario is not None:
        claves.append(f"login:cuenta:{usuario.id}")
    normalizado = normalizar_username(identificador)
    if normalizado:
        claves.append(f"login:cuenta:txt:{normalizado}")

    ip = request.remote_addr or "sin-ip"
    return claves, f"login:ip:{ip}"


def _espera_del_login(usuario, identificador):
    """Segundos que faltan para poder volver a intentar. Cero si esta libre."""
    cfg = current_app.config
    ventana = cfg["LOGIN_VENTANA_SEGUNDOS"]
    bloqueo = cfg["LOGIN_BLOQUEO_SEGUNDOS"]
    claves_cuenta, clave_ip = _claves_del_intento(usuario, identificador)

    esperas = [
        rate_limit.segundos_de_bloqueo(
            clave, cfg["LOGIN_MAX_FALLOS_POR_CUENTA"], bloqueo, ventana
        )
        for clave in claves_cuenta
    ]
    esperas.append(
        rate_limit.segundos_de_bloqueo(
            clave_ip, cfg["LOGIN_MAX_FALLOS_POR_IP"], bloqueo, ventana
        )
    )
    return max(esperas)


def _anotar_login_fallido(usuario, identificador):
    ventana = current_app.config["LOGIN_VENTANA_SEGUNDOS"]
    claves_cuenta, clave_ip = _claves_del_intento(usuario, identificador)
    for clave in claves_cuenta + [clave_ip]:
        rate_limit.registrar_fallo(clave, ventana)


def _anotar_login_exitoso(usuario, identificador):
    """Limpia los contadores de la cuenta que acaba de entrar bien.

    Los DOS de cuenta, porque los dos se ensuciaron al fallar; si quedara el de
    texto, cuatro errores de tipeo y un acierto dejarian a esa persona a un
    intento del bloqueo.

    La clave de IP NO se limpia: si entrar borrara tambien la de la direccion,
    un atacante con una cuenta propia se limpiaria la marca cada veinte
    intentos y el limite por IP no existiria.
    """
    claves_cuenta, _ = _claves_del_intento(usuario, identificador)
    for clave in claves_cuenta:
        rate_limit.limpiar(clave)


def _mensaje_de_espera(segundos):
    """El texto que ve quien quedo bloqueado.

    No dice cual de los dos limites salto ni si el usuario existe: es el mismo
    cartel para todos, para no regalar informacion en el unico momento en que
    el sistema le contesta distinto a un atacante.
    """
    minutos = max(1, -(-segundos // 60))  # hacia arriba
    return (
        "Demasiados intentos fallidos. Por seguridad, esperá "
        f"{minutos} minuto{'s' if minutos != 1 else ''} y volvé a probar."
    )

# ============
#  VISTAS HTML (sesiones tradicionales)
# ============

@auth.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        rol = _rol_pedido(request.form.get("rol"))
        # Se normaliza a minusculas para que Tomy@x.com y tomy@x.com sean el
        # mismo usuario, tanto al registrar como al consultar unicidad.
        email = request.form.get("email", "").strip().lower()

        error = None

        username_error = validate_username(username)
        if username_error:
            error = username_error
        elif not password:
            error = "Se requiere una contraseña"
        else:
            error = validate_email(email) or validate_password(password)

        # Unicidad
        if error is None and User.existe_username_equivalente(username):
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

        # El usuario se busca ANTES del chequeo porque la clave de cuenta sale
        # de su id y no del texto que llego (ver _claves_del_intento). Lo que
        # importa es que lo caro -- el hash -- siga estando DESPUES: al
        # bloqueado el intento le cuesta un SELECT y nada mas.
        user = User.query.filter_by(username=username).first()

        espera = _espera_del_login(user, username)
        if espera:
            flash(_mensaje_de_espera(espera))
            return render_template('auth/login.html'), 429, {"Retry-After": str(espera)}

        error = None
        # Se lleva aparte del mensaje y no se deduce de el: lo que decide si el
        # intento suma al contador es si la CREDENCIAL estaba mal, y "usuario
        # suspendido" es el unico error que llega con la credencial bien.
        credencial_erronea = False

        if user is None:
            error = "El usuario es incorrecto"
            credencial_erronea = True
        elif not check_password_hash(user.password, password):
            error = "La contraseña es incorrecta"
            credencial_erronea = True
        elif user.is_banned:
            error = "Esta cuenta fue suspendida. Contactate con soporte."

        if error is None:
            _anotar_login_exitoso(user, username)
            session.clear()
            session["user_id"] = user.id
            return redirect(url_for('index'))

        # La suspendida no suma: la contrasenia era la correcta, no hay nada
        # que adivinar, y contarla dejaria a esa persona bloqueada ademas de
        # suspendida por reintentar. Pero OJO con el orden del if de arriba:
        # una cuenta suspendida CON la clave mal cae en "la contraseña es
        # incorrecta", asi que si esto preguntara por user.is_banned en vez de
        # por la credencial, una cuenta baneada conocida seria un blanco para
        # probar claves sin gastar el contador de la IP.
        if credencial_erronea:
            _anotar_login_fallido(user, username)

        flash(error)

    return render_template('auth/login.html')


@auth.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    user = User.query.get(user_id) if user_id else None

    # is_banned solo se chequeaba en el login: si banean a alguien mientras
    # navega, seguia con acceso hasta que la sesion expirara sola. Se corta
    # ahora, en cada request.
    if user is not None and user.is_banned:
        session.clear()
        user = None

    g.user = user


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
    rol = _rol_pedido(data.get("rol"))

    errors = []
    username_error = validate_username(username)
    if username_error: errors.append(username_error)
    email_error = validate_email(email)
    if email_error: errors.append(email_error)
    if not password:
        errors.append("password requerido")
    else:
        password_error = validate_password(password)
        if password_error:
            errors.append(password_error)
    if User.existe_username_equivalente(username): errors.append("username ya existe")
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

    # El mismo freno que el formulario y, desde que la clave de cuenta sale del
    # id del usuario, EL MISMO CONTADOR: antes esta puerta contaba por email y
    # la otra por username, asi que alternandolas entraban diez contrasenias
    # erradas contra la misma persona en vez de cinco.
    user = User.query.filter_by(email=email).first()

    espera = _espera_del_login(user, email)
    if espera:
        return (
            jsonify({"error": _mensaje_de_espera(espera)}),
            429,
            {"Retry-After": str(espera)},
        )

    if not user or not check_password_hash(user.password, password):
        _anotar_login_fallido(user, email)
        return jsonify({"error": "credenciales inválidas"}), 401
    if user.is_banned:
        return jsonify({"error": "Esta cuenta fue suspendida."}), 403

    _anotar_login_exitoso(user, email)

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

# GAP CONOCIDO Y ACEPTADO POR AHORA: is_banned solo se chequea al emitir el
# token (api_login), no en cada request. A diferencia de la sesion HTML
# (ver load_logged_in_user, que si revalida en cada request), un usuario
# baneado con un JWT ya emitido conserva acceso hasta que expire
# (JWT_ACCESS_TOKEN_EXPIRES, 1h por default). /auth/me y cualquier endpoint
# con role_required() tienen este mismo gap. No se soluciona aca porque hoy
# no hay endpoints JWT sensibles (la app real es HTML+sesion); si en algun
# momento se agrega uno que si lo sea, ahi conviene revisar en serio (por
# ejemplo, chequeando is_banned en cada request via un callback de
# flask-jwt-extended, o acortando el tiempo de expiracion).


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
