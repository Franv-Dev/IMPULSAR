"""Configuracion de la aplicacion, separada por entorno.

Antes era un script plano con variables sueltas, asi que no habia forma de
tener valores distintos para desarrollo, testing y produccion sin duplicar
codigo. Ahora cada entorno es una clase que hereda de Config.

Cual se usa lo decide la variable de entorno FLASK_ENV (development por
defecto), o el parametro que se le pase a create_app().
"""

import os
from datetime import timedelta

from dotenv import load_dotenv

from services.uploads import MAX_IMAGE_BYTES

load_dotenv()


def _raiz_del_proyecto():
    """La carpeta del repo, encontrada subiendo hasta dar con static/.

    No se usa current_app.root_path (que es la carpeta del modulo que crea la
    Flask) ni el directorio de este archivo: los dos dan por sentado donde vive
    el codigo, y el codigo se va a mudar a un paquete. Lo que no se mueve es
    static/ y las carpetas hermanas (migrations/, scripts/, tests/), asi que la
    raiz se busca por ahi y el resultado no cambia aunque config.py termine tres
    niveles mas adentro.
    """
    actual = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isdir(os.path.join(actual, "static")):
            return actual
        padre = os.path.dirname(actual)
        if padre == actual:
            raise RuntimeError(
                "No se encontro la raiz del proyecto: ninguna carpeta padre de "
                f"{__file__} tiene un static/. Se puede fijar a mano con la "
                "variable de entorno RAIZ_PROYECTO."
            )
        actual = padre


# Se puede fijar a mano, que es lo que necesita un deploy donde el codigo y los
# archivos subidos no viven juntos (un volumen montado aparte, por ejemplo).
RAIZ_PROYECTO = os.getenv("RAIZ_PROYECTO") or _raiz_del_proyecto()


def _build_database_uri():
    """Arma la URI de conexion a MySQL a partir de las variables de entorno.

    Si existe DATABASE_URL se usa tal cual: es lo que suelen inyectar los
    servicios de deploy (Render, Railway) y tiene prioridad.
    """
    url_completa = os.getenv("DATABASE_URL")
    if url_completa:
        return url_completa

    user = os.getenv("DB_USER", "")
    password = os.getenv("DB_PASSWORD", "")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    database = os.getenv("DB_NAME", "")

    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"


class Config:
    """Valores comunes a todos los entornos."""

    SECRET_KEY = os.getenv("SECRET_KEY")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

    SQLALCHEMY_DATABASE_URI = _build_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Rutas absolutas, calculadas desde la raiz del repo y no desde donde vive
    # el modulo que crea la app. Antes cada vista se armaba la suya con
    # current_app.root_path (habia seis copias): si el codigo se muda a un
    # paquete, root_path deja de ser la raiz y las imagenes ya subidas quedan
    # colgadas. Se pasan explicitas a Flask en create_app().
    STATIC_FOLDER = os.path.join(RAIZ_PROYECTO, "static")
    TEMPLATES_FOLDER = os.path.join(RAIZ_PROYECTO, "templates")
    # Donde se guardan las imagenes que suben los usuarios. Se lee con
    # services.uploads.carpeta_uploads(), que es el unico lugar que la arma.
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER") or os.path.join(STATIC_FOLDER, "uploads")
    # Donde van las subidas que NO son publicas: hoy la foto de una solicitud de
    # presupuesto y el documento de un pedido de verificacion (una matricula con
    # nombre y numero real). Se leen con services.uploads.carpeta_privada().
    #
    # HERMANA de static/ y no una subcarpeta de UPLOAD_FOLDER, que es lo que
    # parecia natural: Flask sirve static_folder RECURSIVAMENTE, asi que
    # static/uploads/privado/doc.png se bajaria por /static/uploads/privado/doc.png
    # sin pasar por ninguna vista. La proteccion de estas dos fotos ya esta en el
    # codigo (ver app/servicios/vistas.py), y esto es la segunda capa: que el
    # archivo tampoco este donde un nginx puesto adelante, o un listado de
    # directorio, lo puedan alcanzar sin preguntarle nada a la app.
    PRIVATE_UPLOAD_FOLDER = os.getenv("PRIVATE_UPLOAD_FOLDER") or os.path.join(
        RAIZ_PROYECTO, "uploads_privados"
    )

    MAPTILER_KEY = os.getenv("MAPTILER_KEY")

    # --- Correo saliente (notificaciones) ---------------------------------
    #
    # SMTP de Gmail, que es la decision de esta vuelta: no hay servicio de
    # correo transaccional contratado y el volumen es de unos pocos mails por
    # dia. Si algun dia hay que mandar de a miles esto se cambia por un
    # proveedor con API, y lo unico que se toca son las variables de abajo.
    #
    # USUARIO Y CLAVE SALEN DEL ENTORNO Y NO TIENEN DEFAULT, a proposito y por
    # el mismo motivo que SECRET_KEY: una credencial hardcodeada termina en el
    # repositorio. La clave ademas NO es la del correo, es una "contraseña de
    # aplicacion" de Google, que se genera y se revoca sin tocar la cuenta.
    #
    # Si faltan, la app arranca igual y las notificaciones no se mandan: lo
    # chequea services/notificaciones_email.py antes de intentar conectar. Es
    # lo que deja correr los tests y una copia local sin credenciales.
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    # APAGADO EXPLICITO, Y NO ES UN DEFAULT REDUNDANTE. Flask-Mail, cuando no
    # encuentra MAIL_DEBUG, usa el DEBUG de la app: en desarrollo eso vale True
    # y smtplib pasa a volcar la conversacion SMTP entera por consola, que
    # incluye el AUTH con el usuario y la contraseña de aplicacion en base64 (o
    # sea, en limpio para cualquiera que lea la terminal o el log) y ademas el
    # cuerpo de cada mail, que son mensajes privados entre dos usuarios. El
    # escenario no es raro: pasa apenas alguien carga sus credenciales reales
    # en su .env para probar un envio.
    MAIL_DEBUG = False
    # De que direccion salen los avisos. Por defecto la misma casilla que
    # autentica: Gmail reescribe el From si no coincide con la cuenta, asi que
    # poner otra cosa no serviria de nada.
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER") or MAIL_USERNAME

    # Tamanio maximo de subida: sin esto un archivo enorme puede agotar la
    # memoria y el disco del servidor.
    MAX_CONTENT_LENGTH = MAX_IMAGE_BYTES

    # Cuanto dura el token de la API. Antes estaba hardcodeado en api_login.
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)

    # Cantidad de emprendimientos por pagina en los listados.
    POSTS_POR_PAGINA = 9

    @classmethod
    def init_app(cls, app):
        """Gancho para validaciones propias de cada entorno."""


class DevelopmentConfig(Config):
    """Para trabajar en tu maquina.

    Tiene claves por defecto a proposito, para que el proyecto arranque recien
    clonado sin configurar nada. Nunca se usan en produccion (ver
    ProductionConfig, que directamente no arranca sin claves reales).
    """

    DEBUG = True
    SECRET_KEY = os.getenv("SECRET_KEY", "clave-solo-para-desarrollo")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-solo-para-desarrollo")


class TestingConfig(Config):
    """Para correr los tests: base en memoria y sin CSRF."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "clave-de-testing-suficientemente-larga-32b"
    JWT_SECRET_KEY = "jwt-de-testing-suficientemente-largo-32b"
    # Los tests postean formularios directamente; el CSRF se prueba aparte,
    # en su propio test, activandolo a mano.
    WTF_CSRF_ENABLED = False

    # Sin credenciales de correo, pase lo que pase. Config las lee del entorno,
    # asi que una maquina con el .env real cargado las heredaria y la suite
    # dependeria de que archivo tiene cada uno delante. Con las tres en None,
    # services/notificaciones_email.py corta antes de tocar la red en cualquier
    # maquina, y el test que necesita probar el envio se las pone a mano.
    MAIL_USERNAME = None
    MAIL_PASSWORD = None
    # Tambien el remitente, que si no se hereda de Config y ahi sale de
    # os.getenv(...) or MAIL_USERNAME: con el .env real cargado, la direccion
    # de Tomy se filtraba a la config de los tests. No se llegaba a mandar
    # nada, pero "sin credenciales pase lo que pase" tiene que valer entero, y
    # una de las tres es una credencial igual.
    MAIL_DEFAULT_SENDER = None
    # El freno de abajo, por si algun dia un test las setea y se olvida de
    # sacarlas: con esto Flask-Mail arma el mensaje pero no abre el socket.
    MAIL_SUPPRESS_SEND = True


class ProductionConfig(Config):
    """Para el servidor real."""

    DEBUG = False

    # EL DOMINIO REAL, Y ES UNA CUESTION DE SEGURIDAD, no de prolijidad. Los
    # mails de notificacion llevan un link armado con url_for(_external=True),
    # y sin SERVER_NAME ese link sale con el host que venga en el header Host
    # de la request. O sea: alguien manda un mensaje con "Host:
    # sitio-falso.example" y el link que le llega por mail a la otra persona
    # apunta a sitio-falso.example, con la ruta correcta de IMPULSAR. Es un
    # phishing firmado por nosotros y mandado desde nuestra casilla.
    #
    # Con SERVER_NAME puesto, url_for ignora el header y usa este valor (esta
    # verificado, no es lo que dice la doc y nada mas). Lo que NO hace en esta
    # version de Werkzeug es filtrar el ruteo: una request con otro Host sigue
    # respondiendo normal, asi que esto no deja afuera al health check que
    # pega por IP ni a nada que hoy funcione.
    #
    # Sale del entorno porque el dominio lo sabe el deploy, no el repo. Si
    # falta, init_app avisa por log y los links vuelven al comportamiento
    # viejo; no corta el arranque, que seria dejar la app abajo por algo que
    # no le impide funcionar.
    SERVER_NAME = os.getenv("SERVER_NAME")
    # Que esos links salgan en https. Sin esto toman el esquema con el que
    # llego la request, que detras de un proxy suele ser http aunque el
    # usuario haya entrado por https.
    PREFERRED_URL_SCHEME = "https"

    # Cookies de sesion mas seguras: solo por HTTPS, no accesibles desde JS y
    # no enviadas en requests que vienen de otro sitio.
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    @classmethod
    def init_app(cls, app):
        """Corta el arranque si faltan claves.

        Antes estas claves tenian un valor por defecto hardcodeado: si te
        olvidabas de configurarlas en el servidor, la app arrancaba igual pero
        con una clave publica y conocida, y cualquiera podia falsificar tokens
        JWT o cookies de sesion. Es mejor no arrancar que arrancar inseguro.
        """
        faltantes = [
            nombre
            for nombre in ("SECRET_KEY", "JWT_SECRET_KEY")
            if not app.config.get(nombre)
        ]
        if faltantes:
            raise RuntimeError(
                "Faltan variables de entorno obligatorias en produccion: "
                + ", ".join(faltantes)
            )

        # Avisa, no corta: sin SERVER_NAME la app anda igual, lo que queda mal
        # es el link de los mails (ver el comentario de la constante). Se
        # loguea al arrancar para que aparezca una sola vez y arriba de todo,
        # y no escondido en el log de un request cualquiera.
        if not app.config.get("SERVER_NAME"):
            app.logger.warning(
                "SERVER_NAME no esta configurado: los links de los mails de "
                "notificacion van a salir con el host que mande cada request, "
                "que se puede falsear."
            )


# Nombre de entorno -> clase de configuracion.
CONFIGURACIONES = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config(nombre=None):
    """Devuelve la clase de configuracion segun el nombre o FLASK_ENV."""
    nombre = nombre or os.getenv("FLASK_ENV") or "default"
    return CONFIGURACIONES.get(nombre, DevelopmentConfig)
